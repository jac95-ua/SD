"""Simple CP Engine: registers to CENTRAL and listens for START_CHARGE commands.
When in Suministrando state, it sends TELEMETRY cada segundo.
"""
import argparse
import asyncio
import random
from protocol import send_msg, recv_msg, make_msg


class CPEngine:
    def __init__(self, cp_id: str, central_host: str, central_port: int):
        self.cp_id = cp_id
        self.host = central_host
        self.port = central_port
        self.writer = None
        self.reader = None
        self.suministrando = False

    async def run(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        # register
        await send_msg(self.writer, make_msg('REGISTER', 'cp', self.cp_id, {'location': 'Demo', 'price_kwh': 0.25}))
        # wait for ack
        ack = await recv_msg(self.reader)
        print('Central response:', ack)

        asyncio.create_task(self._read_loop())
        # also listen stdin to toggle suministro
        asyncio.create_task(self._stdin_loop())
        while True:
            if self.suministrando:
                kw = round(random.uniform(3.0, 22.0), 2)
                amount = round(kw * 0.25, 2)
                await send_msg(self.writer, make_msg('TELEMETRY', 'cp', self.cp_id, {'kw': kw, 'amount': amount, 'state': 'Suministrando'}))
            await asyncio.sleep(1)

    async def _read_loop(self):
        while True:
            msg = await recv_msg(self.reader)
            if msg is None:
                print('Conexion cerrada por central')
                break
            tipo = msg.get('tipo')
            if tipo == 'START_CHARGE':
                print('Iniciando suministro por orden de central')
                self.suministrando = True
            elif tipo == 'STOP_CHARGE':
                print('Parando suministro')
                self.suministrando = False
            else:
                print('RECIBIDO CP:', msg)

    async def _stdin_loop(self):
        loop = asyncio.get_running_loop()
        while True:
            # run blocking input in executor
            line = await loop.run_in_executor(None, input, "(CP) pulsar Enter para toggle suministro, q para salir> ")
            if line.strip().lower() == 'q':
                print('Saliendo CP Engine')
                self.writer.close()
                await self.writer.wait_closed()
                break
            else:
                self.suministrando = not self.suministrando
                print('suministrando=', self.suministrando)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=9000, type=int)
    args = parser.parse_args()
    engine = CPEngine(args.id, args.host, args.port)
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        print('CP Engine detenido')
