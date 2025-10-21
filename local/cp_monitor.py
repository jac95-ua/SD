"""Simple CP Monitor: connects to CP Engine (simulated) and sends HEALTH/FAULT to central via the engine.
For MVP this monitor will simulate sending a KO to the engine which the engine forwards to central by a message.
"""
import argparse
import asyncio
import random
from protocol import send_msg, recv_msg, make_msg


async def monitor_loop(cp_id: str, host: str, port: int):
    reader, writer = await asyncio.open_connection(host, port)
    print('Monitor conectado al central (a traves del mismo endpoint en MVP)')
    # for MVP we'll simply send periodic HEALTH messages
    try:
        while True:
            if random.random() < 0.02:
                # simulate fault
                await send_msg(writer, make_msg('HEALTH', 'monitor', cp_id, {'status': 'KO'}))
                print('Monitor: enviado KO')
            else:
                await send_msg(writer, make_msg('HEALTH', 'monitor', cp_id, {'status': 'OK'}))
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        writer.close()
        await writer.wait_closed()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=9000, type=int)
    args = parser.parse_args()
    try:
        asyncio.run(monitor_loop(args.id, args.host, args.port))
    except KeyboardInterrupt:
        print('Monitor detenido')
