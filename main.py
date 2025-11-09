# Import modules needed tkinter and sqlite3

import tkinter
from tkinter import *
from tkinter import messagebox

import sqlite3

# Setup Database - this is going to be stored locally, future upgrade, point this to an WebDAV file structure.
# Setup filename for database and connect sqlite3 to it.

conn = sqlite3.connect('steeletodo.db')
# Check if the database already exists and has data in it. If it is empty or does not exist, set it up and add something to it.
conn.execute('''CREATE TABLE IF NOT EXISTS todo(id INTEGER PRIMARY KEY, task TEXT NOT NULL);''')

# Define our Global Functions
# Show our todo List
def show()
    query = "SELECT * FROM todo;"
    conn.execute(query,(task,))
    return conn.execute(query)
def insertdata(task)

