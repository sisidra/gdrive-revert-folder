import os.path
import sys

import google
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive"]


def list(service, parent):
    fs = service.files()
    fields = "nextPageToken, files(id, name, mimeType, modifiedTime)"
    q = f"'{parent}' in parents and trashed = false"

    files = {parent: {}}
    page_token = None
    while True:
        response = fs.list(pageSize=100, fields=fields, q=q, pageToken=page_token)
        response = response.execute()

        for file in response.get('files', []):
            if file["mimeType"] == "application/vnd.google-apps.folder":
                files.update(list(service, parent=file["id"]))
            else:
                ids = files[parent].get(file["name"], [])
                ids.append(file)
                files[parent][file["name"]] = ids
        page_token = response.get("nextPageToken", None)
        if page_token is None:
            break
    return files


def revert_versions(service, files, ts):
    rev = service.revisions()
    fs = service.files()

    files.sort(key=lambda f: f["modifiedTime"])
    to_delete = files[0:-1]
    to_revert = files[-1]

    for file in to_delete:
        print(f"DELETING: {file}")
        dr = fs.delete(fileId=file['id']).execute()
        print(f"DELETED: {dr}")


    if to_revert["modifiedTime"] > ts:
        response = rev.list(fileId=to_revert["id"], pageSize=100).execute()
        revisions = response.get("revisions", [])
        revisions.sort(key=lambda r: r["modifiedTime"], reverse=True)
        for revision in response.get("revisions", []):
            if revision["modifiedTime"] > ts:
                print(f"DELETING: {revision}")
                dr = rev.delete(fileId=to_revert["id"], revisionId=revision["id"]).execute()
                print(f"DELETED: {dr}")
            else:
                print("DONE WITH REVS LEFT")
                break

def main(folder: str, ts: str):
    creds = google.auth.default()
    service = build("drive", "v3", credentials=creds)

    items = list(service, folder)

    for folder, files_map in items.items():
        for name, files in files_map.items():
            revert_versions(service, files, ts)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("python main.py [folderId] [keep-before RFC 3339 date-time]")
        sys.exit(1)
    
    main(folder=sys.argv[1], ts=sys.argv[2])

