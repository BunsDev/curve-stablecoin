import sys
import boa
import os
import json
import networks
from getpass import getpass
import curve_dao
from eth_account import account
from curve_dao.addresses import CURVE_DAO_OWNERSHIP as target


CONTROLLER = "0xB536FEa3a01c95Dd09932440eC802A75410139D6"
MPOLICY = "0xf574cBeBBd549273aF82b42cD0230DE9eA6efEF7"


def account_load(fname):
    path = os.path.expanduser(os.path.join('~', '.brownie', 'accounts', fname + '.json'))
    with open(path, 'r') as f:
        pkey = account.decode_keyfile_json(json.load(f), getpass())
        return account.Account.from_key(pkey)


if __name__ == '__main__':
    if '--fork' in sys.argv[1:]:
        boa.env.fork(networks.NETWORK)
        boa.env.eoa = '0xbabe61887f1de2713c6f97e567623453d3C79f67'
    else:
        babe = account_load('babe')
        boa.set_network_env(networks.NETWORK)
        boa.env.add_account(babe)
        boa.env._fork_try_prefetch_state = False

    actions = [
        (CONTROLLER, 'set_monetary_policy', MPOLICY)
    ]
    vote_id = curve_dao.create_vote(
        target,
        actions,
        "Set monetary policy for the new sUSDe LlamaLend market, accourding to [https://gov.curve.fi/t/susde-llamalend-market-for-up-to-35x-leverage-with-a-special-monetary-policy/10132/]",
        networks.ETHERSCAN_API_KEY,
        networks.PINATA_TOKEN
    )
    print(vote_id)

    if '--fork' in sys.argv[1:]:
        # Simulating the vote
        assert curve_dao.simulate(vote_id, target['voting'], networks.ETHERSCAN_API_KEY)
