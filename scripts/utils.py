import boa
from vyper.utils import SizeLimits


BLOCK_DURATION = 12  # seconds


def deploy_setup(contract_folder: str = "contracts") -> dict:

    deployer = boa.env.generate_address("fiddy")
    
    # deploy contracts:
    with boa.env.prank(deployer):
        frxeth = boa.load(
            f"{contract_folder}/ERC20.vy",
            "Frax ETH",
            "frxETH",
            18
        )
        
        pool_token = boa.load(
            f"{contract_folder}/LPToken.vy",
            "Curve.fi ETH/frxETH",
            "frxETHCRV",
        )
        
        frxeth_pool = boa.load(
            f"{contract_folder}/FRXETHStableSwap.vy",
            deployer,
            ["0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", frxeth.address],
            pool_token.address,
            120, # A
            4000000, # _fee
            5000000000, # _admin_fee
        )
        
        pool_token.set_minter(frxeth_pool)
    
    return {
        "deployer": deployer,
        "pool": frxeth_pool,
        "pool_token": pool_token,
        "coins": ["0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE", frxeth]
    }
    

def set_balances(addr: str, setup_dict: dict, amount: int = 10**40):
    for coin in setup_dict["coins"]:
        if coin == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
            boa.env.set_balance(addr, amount)
        else:
            coin._mint_for_testing(addr, amount)


def get_balances(addr: str, setup_dict: dict):
    
    eth_balance = boa.env.get_balance(addr)
    frxeth_balance = setup_dict["coins"][1].balanceOf(addr)
    
    return eth_balance, frxeth_balance


def sim_add_liquidity(addr: str, setup_dict: dict, amount: int = 10**30):

    pool = setup_dict["pool"]
    frxeth = setup_dict["coins"][1]

    with boa.env.prank(addr):
        frxeth.approve(pool.address, SizeLimits.MAX_UINT256)
        pool.add_liquidity(
            [amount, amount], 
            0, 
            value=amount
        )


def time_travel(seconds: int = BLOCK_DURATION):
    
    boa.env.vm.patch.timestamp += seconds
    boa.env.vm.patch.block_number += seconds // BLOCK_DURATION
