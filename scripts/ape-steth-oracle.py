from ape import project, accounts, networks
from ape.cli import NetworkBoundCommand, network_option
# account_option could be used when in prod?
import click

from dotenv import load_dotenv
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(Path(BASE_DIR, ".env"))


TRICRYPTO = ["0x7F86Bf177Dd4F3494b841a37e810A34dD56c829B", "0xf5f5B97624542D72A9E06f04804Bf81baA15e2B4"]  # USDC, USDT
CRVUSD_POOLS = ["0x4DEcE678ceceb27446b35C672dC7d61F30bAD69E", "0x390f3595bca2df7d23783dfd126427cceb997bf4"]  # USDC, USDT
STETH_POOL = "0x21e27a5e5513d6e65c4f830167390997aa84843a"
WSTETH = "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"
AGG = "0xe5Afcf332a5457E8FafCD668BcE3dF953762Dfe7"
FACTORY = "0xC9332fdCB1C491Dcc683bAe86Fe3cb70360738BC"
CHAINLINK_ETH = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
CHAINLINK_STETH = "0x86392dC19c0b719886221c78AB11eb8Cf5c52812"
BOUND_SIZE = int(0.015 * 1e18)


@click.group()
def cli():
    """
    Script for deploying wstETH oracle
    """


@cli.command(
    cls=NetworkBoundCommand,
)
@network_option()
def deploy(network):
    account = accounts.load('babe')
    account.set_autosign(True)

    max_fee = networks.active_provider.base_fee * 2
    max_priority_fee = int(0.5e9)
    kw = {'max_fee': max_fee, 'max_priority_fee': max_priority_fee}

    with accounts.use_sender(account):
        account.deploy(
                project.CryptoWithStablePriceWsteth,
                TRICRYPTO,
                [1, 1],  # price index with ETH
                CRVUSD_POOLS,  # CRVUSD stableswaps
                STETH_POOL,  # staked swap (steth/eth)
                AGG,
                FACTORY,
                WSTETH,
                CHAINLINK_ETH,
                CHAINLINK_STETH,
                BOUND_SIZE,
                **kw)
