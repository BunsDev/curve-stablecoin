import pytest
import boa
from boa.vyper.contract import BoaError
from hypothesis import given, settings
from hypothesis import strategies as st
from datetime import timedelta
from vyper.utils import abi_method_id
from ..conftest import approx


N = 5


def get_method_id(desc):
    return abi_method_id(desc).to_bytes(4, 'big') + b'\x00' * 28


@pytest.fixture(scope="module")
def fake_leverage(stablecoin, collateral_token, market_controller, admin):
    # Fake leverage testing contract can also be used to liquidate via the callback
    with boa.env.prank(admin):
        leverage = boa.load('contracts/testing/FakeLeverage.vy', stablecoin.address, collateral_token.address,
                            market_controller.address, 3000 * 10**18)
        boa.env.set_balance(admin, 1000 * 10**18)
        collateral_token._mint_for_testing(leverage.address, 1000 * 10**18)
        return leverage


@pytest.fixture(scope="module")
def controller_for_liquidation(stablecoin, collateral_token, market_controller, market_amm,
                               price_oracle, monetary_policy, admin, accounts):
    def f(sleep_time, discount):
        user = admin
        fee_receiver = accounts[0]  # same as liquidator
        collateral_amount = 10**18
        with boa.env.prank(admin):
            market_controller.set_amm_fee(0)
            monetary_policy.set_rate(int(1e18 * 1.0 / 365 / 86400))  # 100% APY
            collateral_token._mint_for_testing(user, collateral_amount)
            stablecoin.approve(market_amm, 2**256-1)
            stablecoin.approve(market_controller, 2**256-1)
            collateral_token.approve(market_controller, 2**256-1)
        debt = market_controller.max_borrowable(collateral_amount, N)

        with boa.env.prank(user):
            market_controller.create_loan(collateral_amount, debt, N)
        health_0 = market_controller.health(user)
        # We put mostly USD into AMM, and its quantity remains constant while
        # interest is accruing. Therefore, we will be at liquidation at some point
        with boa.env.prank(user):
            market_amm.exchange(0, 1, debt, 0)
        health_1 = market_controller.health(user)

        assert approx(health_0, health_1, 1e-6)

        boa.env.time_travel(sleep_time)

        health_2 = market_controller.health(user)
        # Still healthy but liquidation threshold satisfied
        assert health_2 < discount
        if discount > 0:
            assert health_2 > 0

        with boa.env.prank(admin):
            # Stop charging fees to have enough coins to liquidate in existence a block before
            monetary_policy.set_rate(0)

            market_controller.collect_fees()
            # Check that we earned exactly the same in admin fees as we need to liquidate
            assert stablecoin.balanceOf(fee_receiver) == market_controller.tokens_to_liquidate(user)

        return market_controller

    return f


def test_liquidate(accounts, admin, controller_for_liquidation, market_amm):
    user = admin
    fee_receiver = accounts[0]

    with boa.env.anchor():
        controller = controller_for_liquidation(sleep_time=80 * 86400, discount=0)
        x = market_amm.get_sum_xy(user)[0]

        with boa.env.prank(fee_receiver):
            with boa.reverts("Slippage"):
                controller.liquidate(user, x + 1)
            controller.liquidate(user, x)


@given(frac=st.integers(min_value=0, max_value=11 * 10**17))
@settings(deadline=timedelta(seconds=1000))
def test_liquidate_callback(accounts, admin, stablecoin, controller_for_liquidation, market_amm, fake_leverage, frac):
    user = admin
    fee_receiver = accounts[0]
    deleverage_method = get_method_id("liquidate(address,uint256,uint256,uint256,uint256[])")  # min_amount for stablecoins
    ld = int(0.02 * 1e18)
    if frac < 10**18:
        f = (10**18 + ld // 2) * frac // (10**18 + ld) // 5 * 5  # The latter part is rounding off for multiple bands
    else:
        f = 10**18

    controller = controller_for_liquidation(sleep_time=80 * 86400, discount=0)
    x = market_amm.get_sum_xy(user)[0]

    with boa.env.prank(fee_receiver):
        # Prepare stablecoins to use for liquidation
        # we do it by borrowing

        with boa.reverts("Slippage"):
            controller.liquidate(user, x + 1)
        b = stablecoin.balanceOf(fee_receiver)
        stablecoin.transfer(fake_leverage.address, b)
        try:
            controller.liquidate_extended(user, int(0.999 * f * x / 1e18), frac, True,
                                          fake_leverage.address, deleverage_method, [])
        except BoaError as e:
            if frac == 0 and "Loan doesn't exist" in str(e):
                pass
            else:
                raise


def test_self_liquidate(accounts, admin, controller_for_liquidation, market_amm, stablecoin):
    user = admin
    fee_receiver = accounts[0]

    with boa.env.anchor():
        controller = controller_for_liquidation(sleep_time=35 * 86400, discount=2.5 * 10**16)

        x = market_amm.get_sum_xy(user)[0]
        with boa.env.prank(fee_receiver):
            stablecoin.transfer(user, stablecoin.balanceOf(fee_receiver))

        with boa.env.prank(accounts[1]):
            with boa.reverts("Not enough rekt"):
                controller.liquidate(user, 0)

        with boa.env.prank(user):
            with boa.reverts("Slippage"):
                controller.liquidate(user, x + 1)

            controller.liquidate(user, x)
