from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    table = db.execute("SELECT symbol, shares FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])

    cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

    user_cash = cash[0]["cash"]

    total = 0

    value = 0

    for row in table:
        symbol = row["symbol"]
        shares = row["shares"]
        stock = lookup(symbol)
        price = stock["price"]
        amount = shares * price
        total = amount
        value = value + total
        db.execute("UPDATE portfolio SET price=:price, total=:total WHERE user_id=:user_id AND symbol=:symbol",
                   price=usd(price), total=usd(total), user_id=session["user_id"], symbol=symbol)

    value = value + user_cash

    index_table = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])

    return render_template("index.html", stocks=index_table, cash=usd(user_cash), total=usd(value))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Ensure stock symbol is provided
        if not request.form.get("symbol"):
            return apology("Must enter stock symbol!", 400)

        # Ensure number of shares is provided
        elif not request.form.get("shares"):
            return apology("Must enter number of shares!", 400)

        # Ensure number of shares is a positive integer
        try:
            if int(request.form.get("shares")) < 1:
                return apology("Number of shares must be greater than 0!", 400)
        except:
            return apology("Number of shares must be greater than 0!", 400)

        stock_found = lookup(request.form.get("symbol"))

        if not stock_found:
            return apology("Invalid stock symbol!", 400)

        amount = int(request.form.get("shares")) * stock_found["price"]

        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

        if not cash or float(cash[0]["cash"]) < amount:
            return apology("Not enough cash!", 403)

        user = session["user_id"]
        symbol = stock_found["symbol"]
        name = stock_found["name"]
        price = stock_found["price"]
        shares = request.form.get("shares")
        total = amount
        time = datetime.now()

        transaction = db.execute("INSERT INTO transactions (user_id, symbol, name, shares, price, total, transacted, type) VALUES\
                                (:user, :symbol, :name, :shares, :price, :total, :time, :ttype)",
                                 user=user, symbol=symbol, name=name, shares=shares, price=usd(price),
                                 total=usd(total), time=time, ttype="BUY")

        user_shares = db.execute("SELECT shares FROM portfolio WHERE user_id = :user_id AND symbol = :symbol",
                                 user_id=session["user_id"], symbol=symbol)

        if not user_shares:
            db.execute("INSERT INTO portfolio (user_id, symbol, name, shares, price, total) VALUES \
                        (:user_id, :symbol, :name, :shares, :price, :total)", user_id=session["user_id"], symbol=symbol,
                       name=name, shares=shares, price=usd(price), total=usd(total))

        else:
            total_shares = int(user_shares[0]["shares"]) + int(shares)

            updated_total = total_shares * stock_found["price"]

            db.execute("UPDATE portfolio SET shares = :total_shares, total = :updated_total WHERE user_id = :user_id AND \
                        symbol = :symbol", total_shares=total_shares, updated_total=updated_total, user_id=session["user_id"],
                       symbol=symbol)

        cash = float(cash[0]["cash"]) - float(total)

        update_cash = db.execute("UPDATE users SET cash = :update WHERE id = :user", update=cash, user=session["user_id"])

        return redirect("/")

    else:

        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    transactions = db.execute("SELECT * FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST
    if request.method == "POST":

        # Ensure Symbol was submitted
        if not request.form.get("symbol"):
            return apology("Must provide symbol", 400)

        quote = lookup(request.form.get("symbol"))

        if not quote:
            return apology("Symbol does not exist", 400)

        return render_template("quoted.html", name=quote["name"], symbol=quote["symbol"], price=usd(quote["price"]))

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmed password was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password must be same with confirmed password!", 400)

        new_user = db.execute("INSERT INTO users (username, hash) VALUES (:username, :pas)",
                              username=request.form.get("username"), pas=generate_password_hash(request.form.get("password")))

        if not new_user:
            return apology("Username taken! Try new username!")

        session["user_id"] = new_user

        return redirect("/")

    else:

        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        # Ensure stock symbol is provided
        if not request.form.get("symbol"):
            return apology("Must enter stock symbol!", 400)

        # Ensure number of shares is provided
        elif not request.form.get("shares"):
            return apology("Must enter number of shares!", 400)

        # Ensure number of shares is a positive integer
        elif int(request.form.get("shares")) < 1:
            return apology("Number of shares must be greater than 0!", 400)

        stock_found = lookup(request.form.get("symbol"))

        if not stock_found:
            return apology("Invalid stock symbol!", 400)

        amount = int(request.form.get("shares")) * stock_found["price"]

        table = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])

        input_symbol = request.form.get("symbol")
        input_shares = int(request.form.get("shares"))

        time = datetime.now()

        total = amount

        shares = db.execute("SELECT shares FROM portfolio WHERE user_id = :user_id AND symbol = :symbol",
                            user_id=session["user_id"], symbol=input_symbol)

        if not shares or input_shares > shares[0]["shares"]:
            return apology("Not enough shares!", 400)

        db.execute("INSERT INTO transactions (user_id, symbol, name, shares, price, total, transacted, type) VALUES \
                    (:user_id, :symbol, :name, :shares, :price, :total, :transacted, :ttype)", user_id=session["user_id"],
                   symbol=stock_found["symbol"], name=stock_found["name"], shares=input_shares, price=usd(stock_found["price"]),
                   total=usd(total), transacted=time, ttype="SELL")

        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])
        user_cash = int(cash[0]["cash"]) + int(total)

        db.execute("UPDATE users SET cash = :user_cash WHERE id = :user_id", user_cash=user_cash, user_id=session["user_id"])

        user_shares = int(shares[0]["shares"]) - int(input_shares)

        if user_shares == 0:
            db.execute("DELETE FROM portfolio WHERE user_id = :user_id AND symbol = :symbol", user_id=session["user_id"],
                       symbol=input_symbol)
        else:
            db.execute("UPDATE portfolio SET shares = :user_shares WHERE user_id = :user_id AND \
                        symbol = :input_symbol", user_shares=user_shares, user_id=session["user_id"], input_symbol=input_symbol)

        return redirect("/")

    else:

        table = db.execute("SELECT * FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])

        return render_template("sell.html", symbols=table)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
