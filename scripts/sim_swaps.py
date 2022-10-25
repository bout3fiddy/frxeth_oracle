import boa
import utils
import pandas as pd
from vyper.utils import SizeLimits


def has_balances(addr: str, setup_dict: dict, threshold: int = 100):
    eth_balance, frxeth_balance = utils.get_balances(addr, setup_dict)
    return eth_balance > threshold and frxeth_balance > threshold


def sim_swaps(
    frxeth_to_eth: bool,
    swapper: str, 
    deploy_setup: dict, 
    swap_amount: int, 
    swap_duration: int, 
    minimum_balance: int, 
    max_swaps: int,
    output_file: str,
):
    pool_contract = deploy_setup["pool"]
    
    data = {
        "block_timestamp": [],
        "price_oracle": [],
        "virtual_price": [],
        "p": [],
        "dx": [],
        "dy": [],
        "pool_eth_balance_before_swap": [],
        "pool_frxeth_balance_before_swap": [],
        "pool_eth_balance_after_swap": [],
        "pool_frxeth_balance_after_swap": [],
        "swap_fee": [],
        "gas_used": [],
    }
    
    with boa.env.prank(swapper):
            
        num_swaps = 0
        while (
            has_balances(swapper, deploy_setup, minimum_balance) and 
            num_swaps < max_swaps
        ):
            
            data["pool_eth_balance_before_swap"].append(pool_contract.balances(0))
            data["pool_frxeth_balance_before_swap"].append(pool_contract.balances(1))
            
            if frxeth_to_eth:
                dy, dy_fee = pool_contract.exchange(
                    1, 0, swap_amount, 0
                )
            else:
                dy, dy_fee = pool_contract.exchange(
                    0, 1, swap_amount, 0, value=swap_amount
                )
            
            num_swaps += 1
            data["gas_used"].append(pool_contract._computation.get_gas_used())
            
            # store data
            data["block_timestamp"].append(boa.env.vm.patch.timestamp)
            data["price_oracle"].append(pool_contract.price_oracle())
            data["virtual_price"].append(pool_contract.get_virtual_price())
            data["p"].append(pool_contract.get_p())
            data["dx"].append(swap_amount)
            data["dy"].append(dy)
            data["pool_eth_balance_after_swap"].append(pool_contract.balances(0))
            data["pool_frxeth_balance_after_swap"].append(pool_contract.balances(1))
            data["swap_fee"].append(dy_fee)

            # time travel swap duration:
            utils.time_travel(swap_duration)

    # write data:
    pd.DataFrame.from_dict(data=data).to_csv(output_file)
    

def main():
    
    deploy_setup = utils.deploy_setup()
    frxeth = deploy_setup["coins"][1]
    
    amount_minted_per_user = 10**30
    amount_liquidity_added = 10**30
    
    # generate liquidity provider:
    liquidity_provider = boa.env.generate_address("liquidity_provider")
    utils.set_balances(
        liquidity_provider, deploy_setup, amount_minted_per_user
    )
    utils.sim_add_liquidity(liquidity_provider, deploy_setup, amount_liquidity_added)    

    # generate swapper:
    swapper = boa.env.generate_address("swapper")
    utils.set_balances(swapper, deploy_setup, amount_minted_per_user)
    with boa.env.prank(swapper):
        frxeth.approve(deploy_setup["pool"], SizeLimits.MAX_UINT256)

    # swap and store data:
    swap_amount = 10**18  # wei
    swap_duration = 12  # seconds, so 1 per block
    minimum_balance = 100  # wei of eth and frxeth
    max_swaps = 10  # max swaps to simulate
    
    # frxeth -> eth swaps:
    with boa.env.anchor():
        frxeth_to_eth = True
        sim_swaps(
            frxeth_to_eth,
            swapper, 
            deploy_setup, 
            swap_amount, 
            swap_duration, 
            minimum_balance, 
            max_swaps, 
            "data/frxeth_eth_swaps.csv"
        )
    
    assert deploy_setup["pool"].balances(0) == amount_liquidity_added
    
    # eth -> frxeth swaps:
    frxeth_to_eth = False
    sim_swaps(
        frxeth_to_eth,
        swapper, 
        deploy_setup, 
        swap_amount, 
        swap_duration, 
        minimum_balance, 
        max_swaps, 
        "data/eth_frxeth_swaps.csv"
    )


if __name__=="__main__":
    main()
