import os
import sys
import json
import datetime
from pathlib import Path
os.environ["DJANGO_SETTINGS_MODULE"] = "__main__"
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="finance-tracker-dev-secret-key-change-in-production",
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": Path(__file__).parent / "finance_tracker.db",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "__main__.FinanceConfig",
        ],
        ROOT_URLCONF="__main__",
        MIDDLEWARE=[
            "django.middleware.common.CommonMiddleware",
        ],
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=False,
    )
import django
import types
import sys
from django.apps import AppConfig

class FinanceConfig(AppConfig):
    name = "finance"
    label = "finance"
    path = str(Path(__file__).parent)
mod = types.ModuleType("finance")
sys.modules["finance"] = mod
django.setup()
from django.db import models

class Transaction(models.Model):
    INCOME = "income"
    EXPENSE = "expense"
    TYPE_CHOICES = [(INCOME, "Income"), (EXPENSE, "Expense")]
    CATEGORY_CHOICES = [
        ("salary",       "Salary"),
        ("freelance",    "Freelance"),
        ("investment",   "Investment"),
        ("bonus",        "Bonus"),
        ("housing",      "Housing"),
        ("food",         "Food & Dining"),
        ("transport",    "Transport"),
        ("health",       "Health"),
        ("entertainment","Entertainment"),
        ("shopping",     "Shopping"),
        ("utilities",    "Utilities"),
        ("education",    "Education"),
        ("other",        "Other"),
    ]
    title      = models.CharField(max_length=200)
    amount     = models.DecimalField(max_digits=14, decimal_places=2)
    type       = models.CharField(max_length=10, choices=TYPE_CHOICES)
    category   = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="other")
    date       = models.DateField()
    note       = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "finance"
        ordering  = ["-date", "-created_at"]

    def to_dict(self):
        return {
            "id":         self.pk,
            "title":      self.title,
            "amount":     str(self.amount),
            "type":       self.type,
            "category":   self.category,
            "date":       self.date.isoformat(),
            "note":       self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

def json_response(data, status=200):
    from django.http import JsonResponse as DJR
    resp = DJR(data, status=status, safe=False)
    resp["Access-Control-Allow-Origin"]  = "*"
    resp["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    resp["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

def parse_body(request):

    try:
        return json.loads(request.body.decode("utf-8"))

    except:
        return {}
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from django.utils.dateparse import parse_date
@csrf_exempt

def transactions(request):

    if request.method == "OPTIONS":
        return json_response({})

    if request.method == "GET":
        limit  = int(request.GET.get("limit",  50))
        offset = int(request.GET.get("offset",  0))
        type_filter = request.GET.get("type")
        cat_filter  = request.GET.get("category")
        qs = Transaction.objects.all()

        if type_filter:
            qs = qs.filter(type=type_filter)

        if cat_filter:
            qs = qs.filter(category=cat_filter)
        total = qs.count()
        rows  = [t.to_dict() for t in qs[offset:offset + limit]]
        return json_response({"count": total, "results": rows})

    if request.method == "POST":
        data = parse_body(request)
        required_fields = ["title", "amount", "type", "date"]
        missing = [f for f in required_fields if not data.get(f)]

        if missing:
            return json_response({"error": f"Missing fields: {missing}"}, status=400)

        try:
            txn = Transaction.objects.create(
                title    = data["title"].strip(),
                amount   = data["amount"],
                type     = data["type"],
                category = data.get("category", "other"),
                date     = parse_date(data["date"]) or datetime.date.today(),
                note     = data.get("note", "").strip(),
            )
            print(f"Created transaction: {txn.title} - ${txn.amount}")
            return json_response(txn.to_dict(), status=201)

        except Exception as exc:
            print("!!! ERROR creating transaction:", exc)
            return json_response({"error": str(exc)}, status=400)
    return json_response({"error": "Method not allowed"}, status=405)
@csrf_exempt

def transaction_detail(request, pk):

    if request.method == "OPTIONS":
        return json_response({})

    try:
        txn = Transaction.objects.get(pk=pk)

    except Transaction.DoesNotExist:
        return json_response({"error": "Not found"}, status=404)

    if request.method == "GET":
        return json_response(txn.to_dict())

    if request.method == "PUT":
        data = parse_body(request)
        for field in ("title", "amount", "type", "category", "note"):

            if field in data:
                setattr(txn, field, data[field])

        if "date" in data:
            txn.date = parse_date(data["date"]) or txn.date
        txn.save()
        print(f"Updated transaction {pk}")
        return json_response(txn.to_dict())

    if request.method == "DELETE":
        txn.delete()
        print(f"Deleted transaction {pk}")
        return json_response({"deleted": True, "id": pk})
    return json_response({"error": "Method not allowed"}, status=405)
@csrf_exempt

def summary(request):

    if request.method == "OPTIONS":
        return json_response({})
    income_total = Transaction.objects.filter(type="income").aggregate(t=Sum("amount"))["t"] or 0
    expense_total = Transaction.objects.filter(type="expense").aggregate(t=Sum("amount"))["t"] or 0
    net = float(income_total) - float(expense_total)
    today = datetime.date.today()
    monthly_data = []
    for delta in range(5, -1, -1):
        y = today.year
        m = today.month - delta

        while m <= 0:
            m += 12
            y -= 1
        label = datetime.date(y, m, 1).strftime("%b '%y")
        inc = Transaction.objects.filter(type="income", date__year=y, date__month=m).aggregate(t=Sum("amount"))["t"] or 0
        exp = Transaction.objects.filter(type="expense", date__year=y, date__month=m).aggregate(t=Sum("amount"))["t"] or 0
        monthly_data.append({
            "month":   label,
            "income":  float(inc),
            "expense": float(exp),
        })
    expense_by_cat = list(
        Transaction.objects.filter(type="expense")
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    category_list = [{"name": c["category"], "amount": float(c["total"])} for c in expense_by_cat]
    savings_rate = round((net / float(income_total) * 100), 1) if income_total else 0
    result = {
        "total_income":   float(income_total),
        "total_expenses": float(expense_total),
        "net_balance":    net,
        "savings_rate":   savings_rate,
        "monthly":        monthly_data,
        "categories":     category_list,
    }
    return json_response(result)
@csrf_exempt

def categories_list(request):
    cats = []
    for value, label in Transaction.CATEGORY_CHOICES:

        if value in ("salary", "freelance", "investment", "bonus"):
            group = "income"
        else:
            group = "expense"
        cats.append({"value": value, "label": label, "group": group})
    return json_response(cats)
from django.urls import path
urlpatterns = [
    path("api/transactions/",          transactions),
    path("api/transactions/<int:pk>/", transaction_detail),
    path("api/summary/",               summary),
    path("api/categories/",            categories_list),
]
SEED_TRANSACTIONS = [
    {"title": "Monthly Salary",         "amount": 7500,  "type": "income",  "category": "salary",        "date": "2026-05-01", "note": "May payroll"},
    {"title": "Freelance — UI Design",  "amount": 1850,  "type": "income",  "category": "freelance",     "date": "2026-05-08"},
    {"title": "Dividend Payout",        "amount": 420,   "type": "income",  "category": "investment",    "date": "2026-05-14"},
    {"title": "Apartment Rent",         "amount": 2100,  "type": "expense", "category": "housing",       "date": "2026-05-02", "note": "May rent"},
    {"title": "Grocery Haul",           "amount": 285,   "type": "expense", "category": "food",          "date": "2026-05-06"},
    {"title": "Restaurant — Dinner",    "amount": 95,    "type": "expense", "category": "food",          "date": "2026-05-11"},
    {"title": "Metro Monthly Pass",     "amount": 90,    "type": "expense", "category": "transport",     "date": "2026-05-03"},
    {"title": "Gym + Wellness",         "amount": 75,    "type": "expense", "category": "health",        "date": "2026-05-04"},
    {"title": "Netflix, Spotify, etc.", "amount": 42,    "type": "expense", "category": "entertainment", "date": "2026-05-05"},
    {"title": "Electricity & Internet", "amount": 130,   "type": "expense", "category": "utilities",     "date": "2026-05-07"},
    {"title": "Online Course",          "amount": 199,   "type": "expense", "category": "education",     "date": "2026-05-16"},
    {"title": "Weekend Shopping",       "amount": 240,   "type": "expense", "category": "shopping",      "date": "2026-05-17"},
    {"title": "Monthly Salary",         "amount": 7500,  "type": "income",  "category": "salary",        "date": "2026-04-01"},
    {"title": "Consulting Bonus",       "amount": 600,   "type": "income",  "category": "bonus",         "date": "2026-04-20"},
    {"title": "Apartment Rent",         "amount": 2100,  "type": "expense", "category": "housing",       "date": "2026-04-02"},
    {"title": "Groceries",              "amount": 310,   "type": "expense", "category": "food",          "date": "2026-04-10"},
    {"title": "Car Service",            "amount": 180,   "type": "expense", "category": "transport",     "date": "2026-04-15"},
    {"title": "Doctor Visit",           "amount": 120,   "type": "expense", "category": "health",        "date": "2026-04-08"},
    {"title": "Streaming + Gaming",     "amount": 55,    "type": "expense", "category": "entertainment", "date": "2026-04-05"},
    {"title": "Utilities",              "amount": 125,   "type": "expense", "category": "utilities",     "date": "2026-04-07"},
    {"title": "Monthly Salary",         "amount": 7500,  "type": "income",  "category": "salary",        "date": "2026-03-01"},
    {"title": "Freelance Project",      "amount": 2200,  "type": "income",  "category": "freelance",     "date": "2026-03-22"},
    {"title": "Stock Dividends",        "amount": 385,   "type": "income",  "category": "investment",    "date": "2026-03-15"},
    {"title": "Apartment Rent",         "amount": 2100,  "type": "expense", "category": "housing",       "date": "2026-03-02"},
    {"title": "Food & Dining",          "amount": 420,   "type": "expense", "category": "food",          "date": "2026-03-18"},
    {"title": "Flight Tickets",         "amount": 540,   "type": "expense", "category": "transport",     "date": "2026-03-10"},
    {"title": "Subscriptions",          "amount": 42,    "type": "expense", "category": "entertainment", "date": "2026-03-05"},
    {"title": "Utilities",              "amount": 140,   "type": "expense", "category": "utilities",     "date": "2026-03-07"},
    {"title": "Monthly Salary",         "amount": 7500,  "type": "income",  "category": "salary",        "date": "2026-02-01"},
    {"title": "Investment Return",      "amount": 520,   "type": "income",  "category": "investment",    "date": "2026-02-14"},
    {"title": "Apartment Rent",         "amount": 2100,  "type": "expense", "category": "housing",       "date": "2026-02-02"},
    {"title": "Valentine's Dinner",     "amount": 155,   "type": "expense", "category": "food",          "date": "2026-02-14"},
    {"title": "Groceries",              "amount": 270,   "type": "expense", "category": "food",          "date": "2026-02-09"},
    {"title": "Metro Pass",             "amount": 90,    "type": "expense", "category": "transport",     "date": "2026-02-03"},
    {"title": "Gym Membership",         "amount": 75,    "type": "expense", "category": "health",        "date": "2026-02-04"},
    {"title": "Utilities",              "amount": 145,   "type": "expense", "category": "utilities",     "date": "2026-02-07"},
    {"title": "Monthly Salary",         "amount": 7500,  "type": "income",  "category": "salary",        "date": "2026-01-01"},
    {"title": "Year-End Bonus",         "amount": 3000,  "type": "income",  "category": "bonus",         "date": "2026-01-05", "note": "Q4 performance bonus"},
    {"title": "Apartment Rent",         "amount": 2100,  "type": "expense", "category": "housing",       "date": "2026-01-02"},
    {"title": "New Year Groceries",     "amount": 320,   "type": "expense", "category": "food",          "date": "2026-01-03"},
    {"title": "Gadget Purchase",        "amount": 680,   "type": "expense", "category": "shopping",      "date": "2026-01-10"},
    {"title": "Utilities",              "amount": 150,   "type": "expense", "category": "utilities",     "date": "2026-01-07"},
    {"title": "Health Insurance",       "amount": 220,   "type": "expense", "category": "health",        "date": "2026-01-08"},
    {"title": "Monthly Salary",         "amount": 7500,  "type": "income",  "category": "salary",        "date": "2025-12-01"},
    {"title": "Freelance Rush Job",     "amount": 900,   "type": "income",  "category": "freelance",     "date": "2025-12-18"},
    {"title": "Apartment Rent",         "amount": 2100,  "type": "expense", "category": "housing",       "date": "2025-12-02"},
    {"title": "Holiday Gifts",          "amount": 560,   "type": "expense", "category": "shopping",      "date": "2025-12-20"},
    {"title": "Holiday Dining",         "amount": 310,   "type": "expense", "category": "food",          "date": "2025-12-25"},
    {"title": "Utilities",              "amount": 165,   "type": "expense", "category": "utilities",     "date": "2025-12-07"},
    {"title": "Subscriptions",          "amount": 42,    "type": "expense", "category": "entertainment", "date": "2025-12-05"},
]

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    from django.db import connection

    with connection.schema_editor() as schema_editor:

        try:
            schema_editor.create_model(Transaction)
            print("Created finance_transaction table")

        except Exception as e:
            print("Table already exists or creation skipped:", e)

    if Transaction.objects.count() == 0:
        for txn_data in SEED_TRANSACTIONS:
            Transaction.objects.create(**txn_data)
        print(f"Seeded {len(SEED_TRANSACTIONS)} demo transactions")
    HOST = "127.0.0.1"
    PORT = "8000"
    print("Run the index.html file")
    execute_from_command_line(["manage.py", "runserver", f"{HOST}:{PORT}", "--noreload"])
