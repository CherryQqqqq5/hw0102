import copy
import json


class RestAPI:
    """A simple REST API for tracking IOUs between users."""

    def __init__(self, database=None):
        if database is None:
            database = {"users": []}
        self.database = copy.deepcopy(database)

    @staticmethod
    def _decode_payload(payload):
        """Decode either a JSON string/bytes payload or an object."""
        if isinstance(payload, (bytes, bytearray)):
            return json.loads(payload.decode("utf-8"))
        if isinstance(payload, str):
            return json.loads(payload)
        return payload

    @staticmethod
    def _calculate_balance(user):
        balance = sum(user["owed_by"].values()) - sum(user["owes"].values())
        if abs(balance) < 1e-9:
            balance = 0.0
        return balance

    @staticmethod
    def _clear_pair(lender, borrower):
        """Remove every direct IOU record between two users."""
        lender_name = lender["name"]
        borrower_name = borrower["name"]

        lender["owes"].pop(borrower_name, None)
        lender["owed_by"].pop(borrower_name, None)
        borrower["owes"].pop(lender_name, None)
        borrower["owed_by"].pop(lender_name, None)

    def _find_user(self, name):
        for user in self.database["users"]:
            if user["name"] == name:
                return user
        return None

    def _record_iou(self, lender, borrower, amount):
        """
        Record a loan from lender to borrower, netting it against any
        existing debt between the pair.
        """
        lender_name = lender["name"]
        borrower_name = borrower["name"]

        # Amount currently owed to the lender minus the amount the lender
        # currently owes.  A positive result means the borrower owes the
        # lender, after adding the new loan.
        net = (
            lender["owed_by"].get(borrower_name, 0.0)
            - lender["owes"].get(borrower_name, 0.0)
            + amount
        )
        if abs(net) < 1e-9:
            net = 0.0

        self._clear_pair(lender, borrower)

        if net > 0:
            lender["owed_by"][borrower_name] = net
            borrower["owes"][lender_name] = net
        elif net < 0:
            lender["owes"][borrower_name] = -net
            borrower["owed_by"][lender_name] = -net

        lender["balance"] = self._calculate_balance(lender)
        borrower["balance"] = self._calculate_balance(borrower)

    def get(self, url, payload=None):
        if url == "/users":
            users = self.database["users"]
            if payload is not None:
                requested = self._decode_payload(payload).get("users", [])
                users = [user for user in users if user["name"] in requested]

            users = sorted(users, key=lambda user: user["name"])
            return json.dumps({"users": copy.deepcopy(users)})

        return None

    def post(self, url, payload=None):
        if url == "/add":
            data = self._decode_payload(payload)
            user = {
                "name": data["user"],
                "owes": {},
                "owed_by": {},
                "balance": 0.0,
            }
            self.database["users"].append(user)
            return json.dumps(copy.deepcopy(user))

        if url == "/iou":
            data = self._decode_payload(payload)
            lender = self._find_user(data["lender"])
            borrower = self._find_user(data["borrower"])
            self._record_iou(lender, borrower, data["amount"])

            lender, borrower = sorted(
                [lender, borrower], key=lambda user: user["name"]
            )
            return json.dumps({"users": copy.deepcopy([lender, borrower])})

        return None
