import os
import sys

from perplexity import Perplexity


def main() -> int:
    if not os.getenv("PERPLEXITY_API_KEY"):
        print("Error: PERPLEXITY_API_KEY is not set.", file=sys.stderr)
        print("Set it in your shell or in /workspaces/Managed-agents/.env.", file=sys.stderr)
        return 1

    client = Perplexity()
    response = client.responses.create(
        model="sonar-pro",
        input="Hello",
    )

    print(f"Response ID: {response.id}")
    print(response.output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
