import os

import re
from cs50 import SQL
import datetime
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

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

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    total = 0
    list = []
    stock_list = db.execute("SELECT * FROM stocks WHERE id=:id", id=session['user_id'])
    for row in stock_list:

        price = round(lookup(row['symbol'])['price'], 2)
        total += price * row['shares']
        list.append(price)

    remaining_cash = round(db.execute("SELECT cash FROM users WHERE id=:user_id", user_id = session["user_id"])[0]['cash'], 2) - total
    total = round(total + remaining_cash, 2)
    return render_template("index.html", stock_list=stock_list, price_list=list, total=total, cash=remaining_cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")

        if not symbol.isalpha():
            return apology("reinput symbol please")

        if not symbol or not lookup(symbol)['symbol']:
            return apology("incorrect/no symbol inputted")

        shares = request.form.get("shares")

        if not shares or not shares.isdigit() or int(shares) < 1:
            return apology("incorrect/no shares inputted")

        stock = lookup(symbol)

        cash = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id = session["user_id"])[0]['cash']
        cash_after = round(cash - float(shares) * stock['price'], 2)

        if cash_after < 0:
            return apology("can't afford")

        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")
        date = now.date()


        # ADD ANOTHER TABLE FOR TOTAL STOCK SHARES, CURRENT PRICE, AND TOTAL VALUE
        current_shares = db.execute("SELECT shares FROM stocks WHERE id = :id AND symbol = :symbol", id=session['user_id'], symbol=symbol)

        if not current_shares:
            db.execute('INSERT INTO stocks(name, symbol, shares, id) VALUES (:name, :symbol, :shares, :id)',
            name=stock['name'], symbol=symbol, shares=shares, id=session['user_id'])
        else:
            current_shares[0]['shares'] += int(shares)
            db.execute('UPDATE stocks SET shares = :shares WHERE id = :id AND symbol = :symbol',
                        shares=current_shares[0]['shares'], id=session['user_id'], symbol=symbol)

        # FOR HISTORY TABLE ADD COLUMN SO THAT WE CAN SEE BOUGHT AND SOLD AND ALSO DATE
        db.execute("INSERT INTO history(id, symbol, shares, price, status, date, time) VALUES (:id, :symbol, :shares, :price, :status, :date, :time)",
                id=session['user_id'], symbol=symbol, shares=shares, price=round(stock['price'], 2), status='Bought', date=date, time=current_time)

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_history = db.execute('SELECT * FROM history WHERE id = :id', id=session['user_id'])
    return render_template("history.html", user_history=user_history)


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
    symbol = request.form.get("symbol")

    if request.method == "POST":
        if not symbol:
            return apology("must provide a symbol")

        stock = lookup(symbol)
        if not stock:
            return apology("must provide valid stock name", 400)

        return render_template("quoted.html", symbol=stock['symbol'], name=stock['name'], price=usd(stock['price']))

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                        username=request.form.get("username"))

        # Ensure username was submitted
        if len(rows) == 1 or not request.form.get("username"):
            return apology("must provide username/username is already taken", 403)

        # Ensure password was submitted
        elif not request.form.get("pwdconfirm") or not request.form.get("password"):
            return apology("must provide/confirm password/passwords don't match", 403)

        elif request.form.get("pwdconfirm") != request.form.get("password"):
            return apology ("passwords do not match")

        special_chars = re.compile('[@_!#$%^&*()<>?/\|}{~:]')

        if not any(char.isalpha() or char.isdigit() for char in request.form.get("password")):
            return apology("Input must contain at least one alphabetic and one numeric character.")

        if (special_chars.search(request.form.get("password")) == None):
            return apology("Input must contain at least one special character")

        username = request.form.get("username")
        hash = generate_password_hash(request.form.get ("password"))
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hash)

        session["user_id"] = db.execute("SELECT * FROM users WHERE username=:username", username=username)[0]['id']

        return redirect ("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        symbol = request.form.get("symbol")

        shares = request.form.get("shares")

        if not shares or not shares.isdigit() or int(shares) < 1:
            return apology("incorrect/no shares inputted")

        stock = lookup(symbol)

        user_info = db.execute("SELECT * FROM stocks WHERE id=:id AND symbol=:symbol", id = session["user_id"], symbol=symbol)

        if not user_info:
            return apology("you do not own this stock")

        if int(shares) > user_info[0]['shares']:
            return apology("you do not own these many stocks")


        current_shares = user_info[0]['shares']
        current_shares -= int(shares)

        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")
        date = now.date()

        if current_shares <= 0:
            db.execute('DELETE FROM stocks WHERE id=:id AND symbol=:symbol', id=session['user_id'], symbol=symbol)
        else:
            db.execute('UPDATE stocks SET shares = :shares WHERE id = :id AND symbol = :symbol',
                        shares=current_shares, id=session['user_id'], symbol=symbol)

        # FOR HISTORY TABLE ADD COLUMN SO THAT WE CAN SEE BOUGHT AND SOLD AND ALSO DATE
        db.execute("INSERT INTO history(id, symbol, shares, price, status, date, time) VALUES (:id, :symbol, :shares, :price, :status, :date, :time)",
                id=session['user_id'], symbol=symbol, shares=shares, price=round(stock['price'], 2), status='Sold', date=date, time=current_time)

        return redirect("/")

    else:
        all_stocks = db.execute("SELECT * FROM STOCKS WHERE id=:id", id=session['user_id'])
        return render_template("sell.html", all_stocks=all_stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
