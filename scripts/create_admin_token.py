"""Create a local demo administrator JWT for the CommuteIQ admin UI.

Run from the project root, for example:
  python scripts/create_admin_token.py --employee-id admin-1 --company-id technova

This is a development helper only. Never expose the demo JWT issuer or local
JWT secret as a production authentication mechanism.
"""
import argparse
from app.core.security import create_token


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local CommuteIQ admin JWT")
    parser.add_argument("--employee-id", default="admin-1")
    parser.add_argument("--company-id", choices=["technova", "datasphere", "cloudaxis"], default="technova")
    args = parser.parse_args()
    print(create_token(args.employee_id, args.company_id, role="admin"))


if __name__ == "__main__":
    main()
