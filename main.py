import random
import requests
import platform
import asyncio
import ast
import json
import os

from web3 import Web3
from web3 import AsyncWeb3
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.client_errors import ClientError
from starknet_py.net.client_models import Call
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.cairo.felt import decode_shortstring
from tabulate import tabulate
from colorama import Fore, Style

from data.rpc import EVM_RPC, OTHER_RPC
from settings import *

clear_text = 'cls' if platform.system().lower() == 'windows' else 'clear'

info = {}

with open('data/abi.json') as file:
    abi = json.load(file)

wallets = []
with open('wallets.txt', 'r') as f:
    for row in f:
        wallet = row.strip()
        if wallet:
            wallets.append(wallet)


async def display_info(display=True, write=False, report=False):
    finding_info = f" Network: {info['0']['network']}  |  Wallets: {len(wallets)}  |  Token: {info['0']['token']}  |  Price: {info['0']['price']}"

    headers = ["#", "Wallet", "Tx Count", "Balance", "Balance USD"]
    table = [[k, i['wallet'], i['nonce'], i['balance'], i['bal_usd']] for k, i in info.items() if k != "0"]
    table.append(['━━━━━', '━'*len(wallets[0]), '━'*10, '━'*13, '━'*13])
    table.append(['Total', '', '', round(info["0"]["total"], 7), round(round(info["0"]["total"] * info["0"]["price"], 3), 8)])

    final_table = tabulate(table, headers, tablefmt='mixed_outline', stralign='center', numalign='center')
    if write:
        with open('result.txt', 'w') as file:
            file.write(finding_info + '\n' + final_table)
    if display:
        os.system(clear_text)
        print(Fore.GREEN + Style.BRIGHT + finding_info + Style.RESET_ALL)
        print(final_table)
    if report:
        with open('report.txt', 'w') as file:
            file.write(finding_info + '\n' + final_table)


async def set_data():
    for num, wallet in enumerate(wallets):
        info[str(num+1)] = {
            "wallet" : wallet,
            "nonce"  : "░░░░░",
            "balance": "░░░░░░░░░░░░░",
            "bal_usd": "░░░░░░░░░░░"
        }
    info["0"] = {
        "network": "░░░░░░░░░",
        "token"  : "░░░░░",
        "price"  : 0,
        "total"  : 0
    }


async def get_chain():
    rpc_list = {}
    for num, item in enumerate(EVM_RPC): rpc_list[num+1] = item
    rpc_list[0] = "Custom"
    print(f'Сhoose a network:\n' + '\n'.join([str(i) + ". " + netw for i, netw in rpc_list.items()]))
    rpc_id = int(input('>>> '))
    info["0"]["network"] = rpc_list[rpc_id]
    return EVM_RPC[rpc_list[rpc_id]] if rpc_id != 0 else custom_rpc


async def get_price(token):
    try:
        response = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={token}USDT')
        data = response.json()
        price = float(data['price'])
    except KeyError:
        price = 0
    return price


async def wallet_data(i, wallet, web3, contract, decimal):
    await asyncio.sleep(random.randint(*sleeping))
    try:
        public = Web3.to_checksum_address(wallet)
    except ValueError:
        os.system(clear_text)
        print(Fore.RED + Style.BRIGHT + 'Проблема з гаманцем. Можливо не вірно вказано тип гаманця в settings.py' + Style.RESET_ALL)
        return

    nonce = await web3.eth.get_transaction_count(public)

    if not check_native:
        try:
            balance_wei = await contract.functions.balanceOf(public).call()
        except:
            balance_wei = await contract.functions.hasMinted(public).call()
        human_readable = balance_wei / 10 ** decimal if not nft else balance_wei
    else:
        balance = await web3.eth.get_balance(public)
        human_readable = float(web3.from_wei(balance, "ether"))

    info["0"]["total"] = round(info["0"]["total"] + float(human_readable), 7)
    info[i]["nonce"] = nonce
    info[i]["balance"] = 0 if human_readable == 0 else ('{:.7f}'.format(round(float(human_readable), 7)) if float(human_readable) < 1 else '{:.4f}'.format(round(float(human_readable), 4)))
    info[i]["bal_usd"] = round(float(human_readable * info["0"]["price"]), 3)
    await display_info()


async def evm():
    global abi
    await set_data()
    rpcs = await get_chain()
    await display_info()
    web3 = None
    symbol = ''
    decimal = 0
    contract = None

    if isinstance(rpcs, str):
        if not rpcs:
            print("Custom RPC not found :(")
            return
        web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpcs, request_kwargs={'proxy': 'http://ps129168:4UUbPVthCo@141.11.252.36:8000'}))

        if not await web3.is_connected():
            print("RPC doesn't work :(")
            return
    else:
        connected = False
        for rpc in rpcs:
            web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc))
            if await web3.is_connected():
                connected = True
                break
        if not connected:
            print("RPCs doesn't work :(")
            return

    if not check_native:
        contract_address = Web3.to_checksum_address(token_for_check)
        contract = web3.eth.contract(address=contract_address, abi=abi)
        try:
            symbol = await contract.functions.symbol().call()
        except:
            with open('data/abi_custom.json') as file:
                abi = json.load(file)
            contract = web3.eth.contract(address=contract_address, abi=abi)
            symbol = None
        if not nft:
            decimal = await contract.functions.decimals().call()
    else:
        with open('data/native.json') as file:
            chains = json.load(file)
        try:
            symbol = chains[str(await web3.eth.chain_id)]
        except KeyError:
            pass

    price = await get_price(symbol)
    if 'USDT' in symbol or 'USDC' in symbol or 'DAI' in symbol:
        price = 1
    elif 'eth' in symbol.lower() and symbol != 'ETH':
        price = await get_price('ETH')
    info["0"]["token"] = symbol
    info["0"]["price"] = price

    await asyncio.gather(*[wallet_data(str(i+1), wallet, web3, contract, decimal) for i, wallet in enumerate(wallets)])
    await display_info(write=True)


async def stark():
    if not check_native and nft:
        print(
            Fore.RED + Style.BRIGHT + 'Не можу перевіряти NFT в мережі Starknet.' + Style.RESET_ALL)
        return
    await set_data()
    await display_info()

    contract_addr = '0x049D36570D4e46f48e99674bd3fcc84644DdD6b96F7C741B1562B82f9e004dC7' if check_native else token_for_check

    client = FullNodeClient(node_url=OTHER_RPC['Starknet'])
    symbol = await client.call_contract(
        call=Call(
            to_addr=contract_addr,
            selector=get_selector_from_name('symbol'),
            calldata=[],
        ),
        block_number='latest',
    )
    symbol = decode_shortstring(symbol[0])
    decimals = await client.call_contract(
        call=Call(
            to_addr=contract_addr,
            selector=get_selector_from_name('decimals'),
            calldata=[],
        ),
        block_number='latest',
    )
    decimals = decimals[0]
    info["0"]["network"] = 'Starknet'
    info["0"]["token"] = symbol

    price = await get_price(symbol)
    if 'USDT' in symbol or 'USDC' in symbol or 'DAI' in symbol:
        price = 1
    elif 'eth' in symbol.lower() and symbol != 'ETH':
        price = await get_price('ETH')

    info["0"]["price"] = price

    for i, wallet in enumerate(wallets):
        n = str(i + 1)
        try:
            nonce = await client.get_contract_nonce(wallet)
        except ClientError:
            print(Fore.RED + Style.BRIGHT + 'Проблема з гаманцем. Можливо не вірно вказано тип гаманця в settings.py' + Style.RESET_ALL)
            return
        try:
            balance = await client.call_contract(
                call=Call(
                    to_addr=contract_addr,
                    selector=get_selector_from_name('balance_of'),
                    calldata=[ast.literal_eval(wallet)],
                ),
                block_number='latest',
            )
        except Exception as ex:
            if "{'error': 'Invalid message selector'}" in str(ex):
                balance = await client.call_contract(
                    call=Call(
                        to_addr=contract_addr,
                        selector=get_selector_from_name('balanceOf'),
                        calldata=[ast.literal_eval(wallet)],
                    ),
                    block_number='latest',
                )
            else:
                print(Fore.RED + Style.BRIGHT + 'Невідома проблема з контрактом.' + Style.RESET_ALL)
                return
        human_readable = balance[0] / 10 ** decimals
        info["0"]["total"] = round(info["0"]["total"] + float(human_readable), 7)
        info[n]["nonce"] = nonce
        info[n]["balance"] = 0 if human_readable == 0 else ('{:.7f}'.format(round(float(human_readable), 7)) if float(human_readable) < 1 else '{:.4f}'.format(round(float(human_readable), 4)))
        info[n]["bal_usd"] = round(float(human_readable * info["0"]["price"]), 3)
        await display_info()
        await asyncio.sleep(random.randint(*sleeping))

    await display_info(write=True)

async def report():
    delete = []
    new_total = 0
    for i, data in info.items():
        if i == '0': continue
        if less_or_more == 'less':
            if float(data['balance']) < report_amount:
                new_total += round(float(data['balance']), 7)
            else:
                delete.append(i)
        elif less_or_more == 'more':
            if float(data['balance']) > report_amount:
                new_total += round(float(data['balance']), 7)
            else:
                delete.append(i)
        else:
            print(Fore.RED + Style.BRIGHT + 'Не вірно вказано варіант для репорту' + Style.RESET_ALL)

    info["0"]["total"] = new_total
    for i in delete: info.pop(i)
    await display_info(display=False, report=True)


async def main():
    try:
        if what == 'evm':
            await evm()
        elif what == 'stark':
            await stark()
        else:
            print(Fore.RED + Style.BRIGHT + 'Не вірно вказано тип гаманця в settings.py' + Style.RESET_ALL)
        if do_report:
            await report()
    except KeyboardInterrupt:
        print('Exit pressed Ctrl+C')
    except asyncio.CancelledError:
        print('Asyncio | The work has been canceled')
    except Exception as e:
        print(f'\nSomething went wrong :(\n\n{e}\n')


if __name__ == '__main__':
    asyncio.run(main())
