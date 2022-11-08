# @version 0.3.7
"""
@title Curve USD Stablecoin
@author CurveFi
"""


event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256

event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256


NAME: public(immutable(String[64]))
SYMBOL: public(immutable(String[32]))


@external
def __init__(_name: String[64], _symbol: String[32]):
    NAME = _name
    SYMBOL = _symbol
