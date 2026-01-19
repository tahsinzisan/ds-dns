# main.py
import asyncio
from state import States
from read import Reader
from write import Writer
from server import Server


def main():
    states = States()
    reader = Reader(states)
    writer = Writer()

    server = Server(reader, writer, states)
    asyncio.run(server.start())


if __name__ == "__main__":
    main()
