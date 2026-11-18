import json


class RestAPI:
    def __init__(self, database=None):
        self.database = database if database is not None else {"users": []}
        self.database.setdefault("users", [])
        for user in self.database["users"]:
            user.setdefault("owes", {})
            user.setdefault("owed_by", {})
            user.setdefault("balance", 0.0)

    @staticmethod
    def _payload(payload):
        if payload is None:
            return {}
        if isinstance(payload, (dict, list)):
            return payload
        try:
            return json.loads(payload)
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def _normalise(url):
        if not isinstance(url, str):
            return url
        path = url.split("?", 1)[0].rstrip("/")
        return path or "/"

    def _find(self, name):
        for user in self.database["users"]:
            if user["name"] == name:
                return user
        raise KeyError(name)

    @staticmethod
    def _view(user):
        owes = dict(user.get("owes", {}))
        owed_by = dict(user.get("owed_by", {}))
        balance = sum(owed_by.values()) - sum(owes.values())
        return {
            "name": user["name"],
            "owes": owes,
            "owed_by": owed_by,
            "balance": float(balance),
        }

    def _views(self, users, sort=False):
        if sort:
            users = sorted(users, key=lambda user: user["name"])
        return [self._view(user) for user in users]

    @staticmethod
    def _refresh(user):
        owes = user.get("owes", {})
        owed_by = user.get("owed_by", {})
        user["balance"] = float(sum(owed_by.values()) - sum(owes.values()))

    @staticmethod
    def _set_debt(user, other, positive_key, negative_key, amount):
        user.setdefault(positive_key, {})
        user.setdefault(negative_key, {})
        if amount > 0:
            user[positive_key][other] = float(amount)
            user[negative_key].pop(other, None)
        elif amount < 0:
            user[negative_key][other] = float(-amount)
            user[positive_key].pop(other, None)
        else:
            user[positive_key].pop(other, None)
            user[negative_key].pop(other, None)

    def get(self, url, payload=None):
        url = self._normalise(url)
        data = self._payload(payload)
        if url != "/users":
            return json.dumps({"error": "unknown endpoint"})

        if not isinstance(data, dict) or data.get("users") is None:
            users = self.database["users"]
        else:
            users = [self._find(name) for name in data["users"]]
            users.sort(key=lambda user: user["name"])
        return json.dumps({"users": self._views(users)})

    def post(self, url, payload=None):
        url = self._normalise(url)
        data = self._payload(payload)
        if not isinstance(data, dict):
            data = {}

        if url == "/add":
            name = data["user"]
            try:
                user = self._find(name)
            except KeyError:
                user = {"name": name, "owes": {}, "owed_by": {}, "balance": 0.0}
                self.database["users"].append(user)
            return json.dumps(self._view(user))

        if url == "/iou":
            lender_name = data["lender"]
            borrower_name = data["borrower"]
            amount = float(data["amount"])
            lender = self._find(lender_name)
            borrower = self._find(borrower_name)

            if lender is borrower:
                return json.dumps({"users": self._views([lender], sort=True)})

            current = (
                lender["owed_by"].get(borrower_name, 0.0)
                - lender["owes"].get(borrower_name, 0.0)
            )
            net = current + amount
            self._set_debt(lender, borrower_name, "owed_by", "owes", net)
            self._set_debt(borrower, lender_name, "owes", "owed_by", net)
            self._refresh(lender)
            self._refresh(borrower)
            return json.dumps({"users": self._views([lender, borrower], sort=True)})

        return json.dumps({"error": "unknown endpoint"})
