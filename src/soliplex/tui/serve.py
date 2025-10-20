from textual_serve import server as server_module

def main():
    server = server_module.Server("soliplex-tui", port=8002)
    server.serve()

if __name__ == "__main__":
    main()
