import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
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


@app.route("/")
@login_required
def index():
    """Show stocks of stocks"""
    # select each symbol owned by the user and it's amount
    users = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])

    portfolio_symbols = db.execute("SELECT * FROM stocks WHERE user_id = :id ", id=session["user_id"])

    # create a temporary variable to store TOTAL worth ( cash + share)
    total_cash = 0

    # update each symbol prices and total
    for portfolio_symbol in portfolio_symbols:
        symbol = portfolio_symbol["symbol"]
        shares = portfolio_symbol["shares"]
        stock = lookup(symbol)
        price = stock["price"]
        total = shares * price
        total_cash += total

        db.execute("UPDATE stocks SET shares = :shares, price=:price, total=:total WHERE user_id=:id AND symbol=:symbol",
                   shares=shares, price=usd(price), total=usd(total), id=session["user_id"], symbol=symbol)

    # update user's cash in users
    updated_cash = db.execute("SELECT cash FROM users WHERE id=:id",
                              id=session["user_id"])

    # update total cash -> cash + shares worth
    total_cash += updated_cash[0]["cash"]

    # print portfolio in index homepage
    updated_portfolio = db.execute("SELECT * FROM stocks WHERE user_id=:id", id=session["user_id"])

    return render_template("index.html", stocks=updated_portfolio, cash=usd(updated_cash[0]["cash"]), total=usd(total_cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        # validate input
        try:
            symbol = lookup(request.form.get("symbol"))
            print(symbol)
            shares = int(request.form.get("shares"))
        except:
            return apology("Input required")

        # if symbol is empty return apology
        if not symbol:
            return apology("enter a valid symbol")

        # if shares is empty
        if not shares or shares <= 0:
            return apology("enter valid amount")

        # if can't afford to buy then error
        amount = db.execute("SELECT cash FROM users WHERE id=:id;", id=session["user_id"])
        current_amount = int(amount[0]['cash'])
        if (shares * symbol['price']) > current_amount:
            return apology("low amount")

        else:
            # obtain user's stock information from stock database

            stocks = db.execute("SELECT * FROM stocks WHERE user_id=:user_id AND symbol=:symbol", user_id=session["user_id"],
                                symbol=symbol["symbol"])
            if not stocks:
                db.execute("INSERT INTO stocks (symbol, name, shares, price, user_id) VALUES (:symbol, :name, :shares, :price, :user_id)",
                           symbol=symbol["symbol"], name=symbol["name"], shares=shares, price=symbol['price'], user_id=session["user_id"])

            else:
                new_shares = stocks[0]["shares"] + shares
                db.execute("UPDATE stocks SET shares= :shares, price = :price, total = :total WHERE user_id=:id AND symbol=:symbol",
                           shares=new_shares, price=symbol['price'], total=shares*symbol['price'], id=session["user_id"], symbol=symbol["symbol"])

        db.execute("INSERT INTO history (symbol, shares, price, date) VALUES (:symbol, :shares, :price, :date)",
                   symbol=symbol['symbol'], shares=shares, price=symbol['price'], date=datetime.datetime.now())
        # update cash
        db.execute("UPDATE users SET cash= cash- :total WHERE id=:id", total=shares*symbol['price'], id=session["user_id"])
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    if request.method == 'GET':
        user = request.args.get("username")

        records = db.execute("SELECT * FROM users WHERE username = :username", username=user)

        if len(records) != 0:
            return jsonify(False)

        else:

            return jsonify(True)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT * from history WHERE user_id=:id", id=session["user_id"])
    print(history)

    return render_template("history.html", history=history)


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
    # use lookup function to get current stock info, given its symbol
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        # check stock exists
        if quote == None:
            return apology("invalid symbol", 400)
        # if successful, display info given by quote list
        return render_template("quoted.html", quote=quote)

    # else if user reached route via GET (as by clicking a link or via redirect)
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

        # Ensure password and confirmation match
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # hash the password and insert a new user in the database
        hash = generate_password_hash(request.form.get("password"))
        new_user_id = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                                 username=request.form.get("username"),
                                 hash=hash)

        # unique username constraint violated?
        if not new_user_id:
            return apology("username taken", 400)

        # Remember which user has logged in
        session["user_id"] = new_user_id

        # Display a flash message
        flash("Registered!")

        # Redirect user to home page
        return redirect("/")

    # else if user reached route via GET
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        return render_template("sell.html")
    else:
        # ensure proper symbol
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Invalid Symbol")

        # ensure proper number of shares
        shares = int(request.form.get("shares"))
        try:
            if shares < 0:
                return apology("Shares must be positive integer")
        except:
            return apology("Shares must be positive integer")

        # select the symbol shares of that user
        user_shares = db.execute("SELECT shares FROM stocks WHERE user_id = :id AND symbol=:symbol",
                                 id=session["user_id"], symbol=stock["symbol"])

        # check if enough shares to sell
        if not user_shares or int(user_shares[0]["shares"]) < shares:
            return apology("Not enough shares")

        # update history of a sell
        db.execute("INSERT INTO history (symbol, shares, price, date) VALUES(:symbol, :shares, :price, :date)",
                   symbol=stock["symbol"], shares=-shares, price=usd(stock["price"]), date=datetime.datetime.now())

        # update user cash (increase)
        db.execute("UPDATE users SET cash = cash + :revenue WHERE id = :id", id=session["user_id"], revenue=stock["price"] * shares)
        # decrement the shares count
        total_shares = int(user_shares[0]["shares"]) - shares
        # if after decrement is zero, delete shares from portfolio
        if total_shares == 0:
            db.execute("DELETE FROM stocks WHERE user_id=:id AND symbol=:symbol", id=session["user_id"],
                       symbol=stock["symbol"])
        # otherwise, update portfolio shares count
        else:
            db.execute("UPDATE stocks SET shares=:shares WHERE id=:id AND symbol=:symbol",
                       shares=total_shares, id=session["user_id"], symbol=stock["symbol"])

        # return to index
        return redirect("index.html")


@app.route("/funds", methods=["GET", "POST"])
@login_required
def funds():
    """Add/substract cash to/from amount"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # accepting decimals
        try:
            amount = float(request.form.get("amount"))
        # ensure only acceptable values are entered
        except:
            return apology("amount must be a real number", 400)

        # update user's available cash
        db.execute("UPDATE users SET cash = cash + :amount WHERE id = :user_id",  amount=amount, user_id=session["user_id"])

        #redirect to homepage
        return redirect("/")

    # User reached route via GET (as by submitting a form via GET)
    else:
        return render_template("funds.html")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
