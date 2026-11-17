import json


class RestAPI:
    def __init__(self, database=None):
        self.database = database if database is not None else {"users": []}
        self.database.setdefault("users", [])
        for user in self.database["users"]:
            user.setdefault("owes", {})
            user.setdefault("owed_by", {})
            self._recalculate(user)

    @staticmethod
    def _payload(payload):
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if isinstance(payload, str):
            return json.loads(payload)
        return payload

    @staticmethod
    def _public(user):
        return {
            "name": user["name"],
            "owes": dict(user["owes"]),
            "owed_by": dict(user["owed_by"]),
            "balance": user["balance"],
        }

    @staticmethod
    def _recalculate(user):
        user["balance"] = float(
            sum(user["owed_by"].values()) - sum(user["owes"].values())
        )

    def _users(self):
        return sorted(self.database["users"], key=lambda user: user["name"])

    def _find(self, name):
        for user in self.database["users"]:
            if user["name"] == name:
                return user
        return None

    def get(self, url, payload=None):
        payload = self._payload(payload)
        if url != "/users":
            raise ValueError("Unknown URL: {}".format(url))

        if payload is None or "users" not in payload:
            users = [self._public(user) for user in self._users()]
        else:
            requested = set(payload["users"])
            users = [
                self._public(user)
                for user in self._users()
                if user["name"] in requested
            ]
        return json.dumps({"users": users})

    def post(self, url, payload=None):
        payload = self._payload(payload) or {}
        if url == "/add":
            name = payload["user"]
            user = self._find(name)
            if user is None:
                user = {
                    "name": name,
                    "owes": {},
                    "owed_by": {},
                    "balance": 0.0,
                }
                self.database["users"].append(user)
            return json.dumps(self._public(user))

        if url == "/iou":
            lender_name = payload["lender"]
            borrower_name = payload["borrower"]
            amount = float(payload["amount"])
            lender = self._find(lender_name)
            borrower = self._find(borrower_name)
            if lender is None or borrower is None:
                raise ValueError("Unknown user in IOU")

            net = amount + lender["owed_by"].get(borrower_name, 0.0) \
                - lender["owes"].get(borrower_name, 0.0)
            lender["owed_by"].pop(borrower_name, None)
            lender["owes"].pop(borrower_name, None)
            borrower["owes"].pop(lender_name, None)
            borrower["owed_by"].pop(lender_name, None)
            if net > 0:
                lender["owed_by"][borrower_name] = net
                borrower["owes"][lender_name] = net
            elif net < 0:
                lender["owes"][borrower_name] = -net
                borrower["owed_by"][lender_name] = -net
            self._recalculate(lender)
            self._recalculate(borrower)

            affected = sorted((lender, borrower), key=lambda user: user["name"])
            return json.dumps({"users": [self._public(user) for user in affected]})

        raise ValueError("Unknown URL: {}".format(url))
