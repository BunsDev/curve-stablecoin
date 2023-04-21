import boa
import pytest
from hypothesis import given
from hypothesis import strategies as st
from ...conftest import approx


def test_create_loan(stablecoin, weth, market_controller, market_amm, accounts):
    user = accounts[0]
    assert market_controller.collateral_token() == weth.address

    with boa.env.anchor():
        with boa.env.prank(user):
            initial_amount = 10**25
            boa.env.set_balance(user, initial_amount)
            c_amount = int(2 * 1e6 * 1e18 * 1.5 / 3000)

            l_amount = 2 * 10**6 * 10**18
            with boa.reverts():
                market_controller.create_loan(c_amount, l_amount, 5, value=c_amount)

            l_amount = 5 * 10**5 * 10**18
            with boa.reverts('Need more ticks'):
                market_controller.create_loan(c_amount, l_amount, 4, value=c_amount)
            with boa.reverts('Need less ticks'):
                market_controller.create_loan(c_amount, l_amount, 400, value=c_amount)

            with boa.reverts("Debt too high"):
                market_controller.create_loan(c_amount // 100, l_amount, 5, value=c_amount // 100)

            # Phew, the loan finally was created
            market_controller.create_loan(c_amount, l_amount, 5, value=c_amount)
            # But cannot do it again
            with boa.reverts('Loan already created'):
                market_controller.create_loan(c_amount, 1, 5, value=c_amount)

            assert stablecoin.balanceOf(user) == l_amount
            assert l_amount == stablecoin.totalSupply() - stablecoin.balanceOf(market_controller)
            assert boa.env.get_balance(user) == initial_amount - c_amount

            assert market_controller.total_debt() == l_amount
            assert market_controller.debt(user) == l_amount

            p_up, p_down = market_controller.user_prices(user)
            p_lim = l_amount / c_amount / (1 - market_controller.loan_discount()/1e18)
            assert approx(p_lim, (p_down * p_up)**0.5 / 1e18, 2 / market_amm.A())

            h = market_controller.health(user) / 1e18 + 0.02
            assert h >= 0.05 and h <= 0.06

            h = market_controller.health(user, True) / 1e18 + 0.02
            assert approx(h, c_amount * 3000 / l_amount - 1, 0.02)


@given(
    collateral_amount=st.integers(min_value=10**9, max_value=10**20),
    n=st.integers(min_value=5, max_value=50),
    f=st.floats(min_value=0, max_value=1)
)
def test_max_borrow_eth_weth(weth, market_controller, accounts, collateral_amount, n, f):
    user = accounts[0]
    max_borrowable = market_controller.max_borrowable(collateral_amount, n)
    with boa.reverts('Debt too high'):
        market_controller.calculate_debt_n1(collateral_amount, int(max_borrowable * 1.001), n)
    weth_amount = min(int(f * collateral_amount), collateral_amount)
    eth_amount = collateral_amount - weth_amount
    boa.env.set_balance(user, collateral_amount)
    with boa.env.prank(user):
        weth.deposit(value=weth_amount)
        weth.approve(market_controller.address, 2**256 - 1)
        market_controller.create_loan(collateral_amount, max_borrowable, n, value=eth_amount)


@pytest.fixture(scope="module")
def existing_loan(market_controller, accounts):
    user = accounts[0]
    c_amount = int(2 * 1e6 * 1e18 * 1.5 / 3000)
    l_amount = 5 * 10**5 * 10**18
    n = 5

    with boa.env.prank(user):
        boa.env.set_balance(user, c_amount)
        market_controller.create_loan(c_amount, l_amount, n, value=c_amount)


def test_repay_all(weth, stablecoin, market_controller, existing_loan, accounts):
    user = accounts[0]
    with boa.env.prank(user):
        c_amount = int(2 * 1e6 * 1e18 * 1.5 / 3000)
        amm = market_controller.amm()
        stablecoin.approve(market_controller, 2**256-1)
        market_controller.repay(2**100, user)  # use_eth is already true
        assert market_controller.debt(user) == 0
        assert stablecoin.balanceOf(user) == 0
        assert boa.env.get_balance(user) == c_amount
        assert stablecoin.balanceOf(amm) == 0
        assert weth.balanceOf(amm) == 0
        assert market_controller.total_debt() == 0


def test_add_collateral(stablecoin, weth, market_controller, existing_loan, market_amm, accounts):
    user = accounts[0]

    c_amount = int(2 * 1e6 * 1e18 * 1.5 / 3000)
    debt = market_controller.debt(user)

    n_before_0, n_before_1 = market_amm.read_user_tick_numbers(user)
    with boa.env.prank(user):
        boa.env.set_balance(user, c_amount)
        market_controller.add_collateral(c_amount, user, value=c_amount)
    n_after_0, n_after_1 = market_amm.read_user_tick_numbers(user)

    assert n_before_1 - n_before_0 + 1 == 5
    assert n_after_1 - n_after_0 + 1 == 5
    assert n_after_0 > n_before_0

    assert market_controller.debt(user) == debt
    assert stablecoin.balanceOf(user) == debt
    assert boa.env.get_balance(user) == 0
    assert stablecoin.balanceOf(market_amm) == 0
    assert weth.balanceOf(market_amm) == 2 * c_amount
    assert market_controller.total_debt() == debt


def test_remove_collateral(stablecoin, weth, market_controller, existing_loan, market_amm, accounts):
    user = accounts[0]
    c_amount = int(2 * 1e6 * 1e18 * 1.5 / 3000)

    with boa.env.prank(user):
        market_controller.remove_collateral(10**6)

    assert boa.env.get_balance(user) == 10**6
    assert weth.balanceOf(market_amm) == c_amount - 10**6
