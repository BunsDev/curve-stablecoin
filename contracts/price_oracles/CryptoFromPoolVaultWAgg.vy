# @version 0.3.10
"""
@title CryptoFromPoolVaultWAgg
@notice Price oracle for pools which contain cryptos and crvUSD. It also references aggregated USD, so works for mint markets.
        In addition, it adds a vault redemption rate. Only suitable for vaults which cannot be affected by donation attack (like sFRAX)
@author Curve.Fi
@license MIT
"""
interface Pool:
    def price_oracle(i: uint256 = 0) -> uint256: view  # Universal method!

interface StableAggregator:
    def price() -> uint256: view
    def price_w() -> uint256: nonpayable
    def stablecoin() -> address: view

interface Vault:
    def convertToAssets(shares: uint256) -> uint256: view


POOL: public(immutable(Pool))
BORROWED_IX: public(immutable(uint256))
COLLATERAL_IX: public(immutable(uint256))
N_COINS: public(immutable(uint256))
NO_ARGUMENT: public(immutable(bool))
VAULT: public(immutable(Vault))
AGG: public(immutable(StableAggregator))


@external
def __init__(
        pool: Pool,
        N: uint256,
        borrowed_ix: uint256,
        collateral_ix: uint256,
        vault: Vault,
        agg: StableAggregator
    ):
    assert borrowed_ix != collateral_ix
    assert borrowed_ix < N
    assert collateral_ix < N
    POOL = pool
    N_COINS = N
    BORROWED_IX = borrowed_ix
    COLLATERAL_IX = collateral_ix
    VAULT = vault
    AGG = agg

    no_argument: bool = False
    if N == 2:
        success: bool = False
        res: Bytes[32] = empty(Bytes[32])
        success, res = raw_call(
            pool.address,
            _abi_encode(empty(uint256), method_id=method_id("price_oracle(uint256)")),
            max_outsize=32, is_static_call=True, revert_on_failure=False)
        if not success:
            no_argument = True
    NO_ARGUMENT = no_argument


@internal
@view
def _raw_price() -> uint256:
    p_borrowed: uint256 = 10**18
    p_collateral: uint256 = 10**18

    if NO_ARGUMENT:
        p: uint256 = POOL.price_oracle()
        if COLLATERAL_IX > 0:
            p_collateral = p
        else:
            p_borrowed = p

    else:
        if BORROWED_IX > 0:
            p_borrowed = POOL.price_oracle(BORROWED_IX - 1)
        if COLLATERAL_IX > 0:
            p_collateral = POOL.price_oracle(COLLATERAL_IX - 1)

    return p_collateral * VAULT.convertToAssets(10**18) / p_borrowed


@external
@view
def price() -> uint256:
    return self._raw_price() * AGG.price() / 10**18


@external
def price_w() -> uint256:
    return self._raw_price() * AGG.price_w() / 10**18
