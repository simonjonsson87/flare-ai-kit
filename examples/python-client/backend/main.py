import asyncio
from .ra_tls_main import main

def start():
    print("Before asuncio.run(main)")
    asyncio.run(main())