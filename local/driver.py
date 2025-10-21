"""Driver client: requests authorization and waits for response from central."""
import argparse
import asyncio
from protocol import send_msg, recv_msg, make_msg


async def run_driver(driver_id: str, cp_id: str, host: str, port: int):
    reader, writer = await asyncio.open_connection(host, port)
    await send_msg(writer, make_msg('AUTH_REQUEST', 'driver', driver_id, {'cp_id': cp_id}))
    resp = await recv_msg(reader)
    print('Respuesta de central:', resp)
    # wait for possible updates
    async def listen():
        while True:
            m = await recv_msg(reader)
            if m is None:
                break
            print('Driver recibido:', m)

    await listen()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', required=True)
    parser.add_argument('--cp', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=9000, type=int)
    args = parser.parse_args()
    try:
        asyncio.run(run_driver(args.id, args.cp, args.host, args.port))
    except KeyboardInterrupt:
        print('Driver detenido')
