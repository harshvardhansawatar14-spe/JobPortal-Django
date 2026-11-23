import json

data = json.load(open("full_local_backup.json", encoding="utf-8-sig"))

skip = {
    "contenttypes.contenttype",
    "auth.permission",
    "auth.group",
    "sessions.session",
    "admin.logentry",
}

data = [x for x in data if x["model"] not in skip]

for x in data:
    if x["model"] == "accounts.user":
        x["fields"]["groups"] = []
        x["fields"]["user_permissions"] = []

order = {
    "accounts.user": 1,
    "accounts.companyprofile": 2,
    "jobs.job": 3,
    "applications.application": 4,
    "jobs.savedjob": 5,
}

data.sort(key=lambda x: order.get(x["model"], 99))

with open("data_restore.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Filtered records:", len(data))
