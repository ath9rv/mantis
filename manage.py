"""
MANTIS Management & CLI Entrypoint
Commands:
  python manage.py run     - Starts FastAPI web server and cockpit at http://localhost:8000
  python manage.py seed    - Populates database with Scenario 1 data
  python manage.py test    - Runs end-to-end scenario checks
"""

import sys
import os
import uvicorn

def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "help"

    if cmd == "run":
        port = int(os.getenv("PORT", 8000))
        host = os.getenv("HOST", "127.0.0.1")
        if host not in {"127.0.0.1", "localhost", "::1"} and not os.getenv("MANTIS_API_KEY"):
            raise SystemExit("Refusing non-local bind without MANTIS_API_KEY configured.")
        print(f"\n[+] Starting MANTIS 2.0 Web Cockpit & API on http://localhost:{port}")
        print(f"    - Swagger API Docs: http://localhost:{port}/docs")
        print(f"    - Interactive Cockpit: http://localhost:{port}/\n")
        uvicorn.run("mantis.api.app:app", host=host, port=port, reload=True)

    elif cmd == "seed":
        import generate_scenario
        print("\n[+] Generating synthetic scenario fixtures...")
        generate_scenario.generate_victim_statement()
        generate_scenario.generate_mule1_statement()
        generate_scenario.generate_mule2_statement()
        generate_scenario.generate_tron_chain_data()
        generate_scenario.generate_cytoscape_mock()
        print("[SUCCESS] Scenario fixtures ready in d:\\Mantis\\data\\scenario_1\n")

    elif cmd == "test":
        import test_pipeline
        test_pipeline.run_e2e_pipeline()

    else:
        print("""
MANTIS CLI Commands:
  python manage.py run   - Launch web dashboard and REST API
  python manage.py seed  - Seed test data fixtures
  python manage.py test  - Run end-to-end scenario checks
        """)

if __name__ == "__main__":
    main()
