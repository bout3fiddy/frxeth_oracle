import os
import typing
import boa
import utils
import pandas as pd
from vyper.utils import SizeLimits
from random import randint, seed, random


def random_swamp_samples(
    a: int = 1, b: int = 10**18, num_steps: int = 1000
):
    """Generates random walk of swap amounts

    y(t) = B0 + B1*X(t-1) + e(t)
    
    Returns:
        List: list of random walk samples
    """
    
    def _sign():
        return -1 if random() < 0.5 else 1
    
    seed(randint(0, 100))
    random_walk = []
    b_0 = _sign() * randint(a, b)
    random_walk.append(b_0)
    
    for i in range(1, num_steps):
        movement = _sign() * randint(a, b)
        value = random_walk[i-1] + movement
        random_walk.append(value)

    return random_walk


def has_balances(addr: str, setup_dict: dict, threshold: int = 100):
    eth_balance, frxeth_balance = utils.get_balances(addr, setup_dict)
    return eth_balance > threshold and frxeth_balance > threshold


def sim_swaps(
    swapper: str, 
    deploy_setup: dict, 
    swamp_sizes: typing.List[int], 
    swap_duration: int, 
    minimum_balance: int, 
    output_file: str = None,
):
    pool_contract = deploy_setup["pool"]
    
    data = {
        "block_timestamp": [],
        "eth_to_frxeth": [],
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
            num_swaps < len(swamp_sizes)
        ):
            
            data["pool_eth_balance_before_swap"].append(pool_contract.balances(0))
            data["pool_frxeth_balance_before_swap"].append(pool_contract.balances(1))
            
            dx = swamp_sizes[num_swaps]
            eth_to_frxeth = 1
            # if dx is negative, we do frxeth -> eth swap (arbitrary choice)
            if swamp_sizes[num_swaps] < 0:
                dy, dy_fee = pool_contract.exchange(
                    1, 0, abs(dx), 0
                )
                eth_to_frxeth = 0
            else:
                dy, dy_fee = pool_contract.exchange(
                    0, 1, dx, 0, value=dx
                )
            
            data["gas_used"].append(pool_contract._computation.get_gas_used())
            
            # store data
            data["block_timestamp"].append(boa.env.vm.patch.timestamp)
            data["eth_to_frxeth"].append(eth_to_frxeth)
            data["price_oracle"].append(pool_contract.price_oracle())
            data["virtual_price"].append(pool_contract.get_virtual_price())
            data["p"].append(pool_contract.get_p())
            data["dx"].append(abs(dx))
            data["dy"].append(dy)
            data["pool_eth_balance_after_swap"].append(pool_contract.balances(0))
            data["pool_frxeth_balance_after_swap"].append(pool_contract.balances(1))
            data["swap_fee"].append(dy_fee)

            # time travel swap duration:
            utils.time_travel(swap_duration)
            num_swaps += 1


    if output_file:
        # write data:
        pd.DataFrame.from_dict(data=data).to_csv(output_file)
    else:
        return data


def main():
    
    deploy_setup = utils.deploy_setup()
    frxeth = deploy_setup["coins"][1]
    
    amount_minted_per_user = 10**25
    amount_liquidity_added = 10**25
    
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

    # sim settings:
    min_swamp_size = 1  # 1 wei
    max_swamp_size = 10**18  # 0.01 ETH/frxETH
    swap_duration = 12  # seconds, so 1 per block
    minimum_balance = 100  # wei of eth and frxeth
    max_swaps = 1000  # max swaps to simulate
    num_random_walks = 1000  # number of random walks to simulate
    
    # get number of random walks stored:
    random_walk_ids = []
    for stored_random_walk in os.listdir("data"):
        if stored_random_walk.startswith("random_swamps"):
            random_walk_ids.append(
                int(stored_random_walk.split("_")[-1].split(".")[0])
            )
    store_start_id = max(random_walk_ids) + 1 if random_walk_ids else 0
    
    # random swamps:
    for random_walk_no in range(num_random_walks):
        
        swamp_sizes = random_swamp_samples(
            min_swamp_size, max_swamp_size, max_swaps
        )
        
        with boa.env.anchor():
            sim_swaps(
                swapper,
                deploy_setup, 
                swamp_sizes, 
                swap_duration,
                minimum_balance,
                f"data/random_swamps_{store_start_id + random_walk_no}.csv"
            )
    


if __name__=="__main__":
    main()
