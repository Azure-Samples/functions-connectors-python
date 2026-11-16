"""Reject invalid OneDrive trigger folder IDs before provisioning resources."""

import os
import sys


def validate_folder_id(folder_id: str) -> None:
    if (not folder_id.strip() or folder_id != folder_id.strip() or
            folder_id.lower() in ("root", "null") or
            any(char in folder_id for char in ('"', "\\", "\r", "\n"))):
        raise ValueError(
            "Set ONEDRIVE_FOLDER_ID to a connector-returned folder ID without surrounding whitespace, quotes, or backslashes. "
            "The literal 'root' fails trigger evaluation with 'Invalid fileId'. "
            "See README: Find a folder ID."
        )


if __name__ == "__main__":
    try:
        validate_folder_id(os.environ.get("ONEDRIVE_FOLDER_ID", ""))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
