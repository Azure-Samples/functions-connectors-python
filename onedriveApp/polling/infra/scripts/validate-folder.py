"""Reject invalid OneDrive trigger folder IDs before provisioning resources."""

import os
import sys


def validate_folder_id(folder_id: str) -> None:
    if not folder_id.strip() or folder_id.strip().lower() in ("root", "null"):
        raise ValueError(
            "Set ONEDRIVE_FOLDER_ID to a connector-returned folder ID with 'azd env set'. "
            "The literal 'root' fails trigger evaluation with 'Invalid fileId'. "
            "See README: Find a folder ID."
        )


if __name__ == "__main__":
    try:
        validate_folder_id(os.environ.get("ONEDRIVE_FOLDER_ID", ""))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
