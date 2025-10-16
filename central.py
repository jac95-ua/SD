"""Minimal CENTRAL server for EVCharging MVP using asyncio and newline-delimited JSON.

Features:
- Accepts REGISTER from CPs and AUTH_REQUEST from drivers.
- Tracks CP state in memory and forwards simple responses.
"""
import argparse
import asyncio
from typing import Dict

from protocol import recv_msg, send_msg, make_msg


class Central:
    def __init__(self):
        # cp_id -> info dict
        self.cps: Dict[str, Dict] = {}

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        print(f'Conexión desde {addr}')
        try:
            while True:
                msg = await recv_msg(reader)
                if msg is None:
                    break
                tipo = msg.get('tipo')
                src = msg.get('source')
                id_ = msg.get('id')
                payload = msg.get('payload', {})

                print('RECIBIDO:', tipo, 'de', src, 'id', id_, payload)

                if tipo == 'REGISTER' and src == 'cp':
                    # mark CP as known and activated when it registers
                    self.cps[id_] = {'info': payload, 'state': 'ACTIVADO', 'writer': writer}
                    await send_msg(writer, make_msg('REGISTER_ACK', 'central', id_, {'status': 'OK'}))
                    print(f'CP registrado: {id_}')

                elif tipo == 'AUTH_REQUEST' and src == 'driver':
                    cp_id = payload.get('cp_id')
                    approved = False
                    if cp_id in self.cps:
                        # simple policy: approve if present
                        approved = True
                        # notify CP if connected
                        cp_writer = self.cps[cp_id].get('writer')
                        if cp_writer:
                            await send_msg(cp_writer, make_msg('START_CHARGE', 'central', cp_id, {'driver_id': id_}))

                    await send_msg(writer, make_msg('AUTH_RESPONSE', 'central', id_, {'approved': approved, 'cp_id': cp_id}))

                elif tipo == 'TELEMETRY' and src == 'cp':
                    # receive telemetry from CP, update internal state and print
                    tel = payload
                    self.cps.setdefault(id_, {}).setdefault('meta', {})['last_telemetry'] = tel
                    print(f"TELEMETRY {id_}:", tel)

                elif tipo == 'HEALTH' and src in ('monitor', 'cp'):
                    status = payload.get('status')
                    print(f'HEALTH {id_}:', status)
                    if status == 'KO':
                        # mark CP as averiado
                        if id_ in self.cps:
                            self.cps[id_]['state'] = 'AVERiado'
                        # optionally notify or take action here

                else:
                    await send_msg(writer, make_msg('ERROR', 'central', id_ or 'unknown', {'message': 'Operacion desconocida'}))

        except Exception as e:
            print('Error en cliente:', e)
        finally:
            writer.close()
            await writer.wait_closed()


async def main(host: str, port: int):
    central = Central()
    server = await asyncio.start_server(central.handle_client, host, port)
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Servidor CENTRAL escuchando en {addrs}')
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', default=9000, type=int)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        print('Central detenido')
