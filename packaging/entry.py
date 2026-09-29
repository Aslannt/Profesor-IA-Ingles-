"""Punto de entrada del .exe (igual que en el Copiloto: congelar el __main__ de un paquete
confunde los imports relativos)."""
from profesora.cliente.__main__ import main

if __name__ == "__main__":
    main()
