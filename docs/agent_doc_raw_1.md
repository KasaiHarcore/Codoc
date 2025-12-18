# 📄 Project Documentation – **OOP‑Student‑Manager**

**File name:** `1st Project OOP.py`  

> *A simple command‑line student management system that uses a MySQL database for persistence and can send an email alert.*  

---  

## 0. Code Overview  

| Aspect | Details |
|--------|---------|
| **Purpose** | Demonstrates basic Object‑Oriented‑Programming (OOP) concepts (although no classes are used) and CRUD operations on a MySQL table `slist`. |
| **Execution entry point** | The script runs `menu()` at the bottom of the file, which displays the main UI and drives the whole program. |
| **Main technologies** | - **MySQL** (`mysql.connector`) – database connectivity.<br>- **SMTP** (`smtplib`, `ssl`, `email.mime`) – sending alert e‑mail.<br>- **Standard library** – `csv`, `sys`, `time`, `os`, `email.mime.*`. |
| **User interaction** | Text‑based menu displayed in the console; the user types a number to choose an action. |
| **Data source** | A MySQL database named **`hocsinh`** with a table **`slist`** (columns: `ID, Name, Age, Address, Email, GPA`). |
| **Global state** | Several global variables hold the DB connection, cursor, fetched data, a hard‑coded list of student names, and a farewell banner. |

---  

## 1. Functions and Global Variables  

### 1.1 Imports  

```python
import mysql.connector               # 3rd‑party – MySQL driver
from mysql.connector import Error, errorcode   # 3rd‑party – error handling (unused)
import smtplib                       # base – SMTP client
import csv                           # base – CSV handling (unused)
import sys                           # base – system utilities
import time                          # base – time formatting
import os                            # base – OS utilities (unused)
import ssl                           # base – SSL context (unused)
from email.mime.text import MIMEText        # base – email building (unused)
from email.mime.multipart import MIMEMultipart  # base – email building (unused)
```

> **Note:** Some imported modules (`csv`, `os`, `ssl`, `MIMEText`, `MIMEMultipart`) are never used in the current code.

### 1.2 Global Variables  

| Variable | Type / Value | Description |
|----------|--------------|-------------|
| `ttdb` | `mysql.connector.MySQLConnection` | Connection object to the MySQL server (`host="localhost", user="DKtahuio", passwd="thanhdat4856", database="hocsinh"`). |
| `ttcursor` | `MySQLCursor` | Cursor created from `ttdb`; used for the initial `SELECT * FROM slist`. |
| `thongtin` | `list[tuple]` | Result of `ttcursor.fetchall()` – all rows from `slist` at program start. |
| `listStd` | `list[str]` | Hard‑coded list of five student names (used only by `List()` for a demo list). |
| `bye` | `str` | A multi‑line banner printed when the user exits. |
| `x`, `y` | `str` | Helper strings used to build `bye`. |

### 1.3 Functions  

Below each function is shown with a **pseudo‑signature** (no type hints in the original code) and a line‑by‑line explanation.

---

#### `main()`

```python
def main():
    menu()
```

* **Purpose** – Simple wrapper that starts the UI.  
* **How it works** – Calls `menu()`; never used elsewhere because the script calls `menu()` directly at the bottom.

---

#### `menu()`

```python
def menu():
    print("""...welcome banner...""")
    print(time.strftime("%c"))
    print("HIIIII!!!!")
    print("This is what i can do and learn in 1 month ^^")
    print("Made by Datdeptraoi :>")
    print("""1: Show Student.\n2: Edit Student.\n3: Sort Student.\n4: Send Alert.\n5: Exit.""")
    choice = input("Please enter your choice:")
    if choice == "1":
        Studentteam()
    elif choice == "2":
        Editting()
    elif choice == "3":
        Sort()
    elif choice == "4":
        Alert()
    elif choice == "5":
        exit()
    else:
        print("You must only select either 1 to 5.")
        print("Please try again.")
        menu()
```

* **Purpose** – Main navigation menu displayed after every completed operation.  
* **Key steps**  
  1. Prints a decorative header and the current date/time (`time.strftime`).  
  2. Shows the list of available actions.  
  3. Reads the user’s choice.  
  4. Dispatches to the appropriate function (`Studentteam`, `Editting`, `Sort`, `Alert`, `exit`).  
  5. On invalid input, recursively calls itself to re‑prompt.

---

#### `Studentteam()`

```python
def Studentteam():
    print("""1:Student list.\n2:Student Infomation.\n3:Return to mainmenu.""")
    choice = input("Please Select An Above Option:")
    if choice == "1":
        List()
    elif choice == "2":
        Info()
    elif choice == "3":
        menu()
    else:
        print("You must only select either 1 to 3.")
        print("Please try again.")
        Studentteam()
```

* **Purpose** – Sub‑menu for read‑only operations.  
* **Calls** – `List()`, `Info()`, or returns to `menu()`.

---

#### `List()`

```python
def List():
    print("List Students\n")
    for students in listStd:
        print("=>{}".format(students))
    Studentteam()
```

* **Purpose** – Shows the hard‑coded `listStd` (demo list).  
* **Flow** – Prints each name, then returns to the `Studentteam` submenu.

---

#### `Info()`

```python
def Info():
    for i in thongtin:
        print(i)
    Studentteam()
```

* **Purpose** – Displays every row fetched from the database at program start (`thongtin`).  
* **Flow** – Iterates over the list of tuples and prints them, then goes back to `Studentteam`.

---

#### `Editting()`

```python
def Editting():
    print("""1: Add Student.\n2: Delete Student.\n3: Edit Stu Info.\n4: Return to mainmenu.""")
    choice = input("Chosse next decision:")
    if choice == "1":
        Adding()
    elif choice == "2":
        Deleting()
    elif choice == "3":
        Change()
    elif choice == "4":
         menu()
    else:
        print("You must only select either 1 to 4.")
        print("Please try again.")
        Editting()
```

* **Purpose** – Sub‑menu for **Create / Delete / Update** operations.  
* **Calls** – `Adding()`, `Deleting()`, `Change()`, or returns to `menu()`.

---

#### `Adding()`

```python
def Adding():
    cursor = ttdb.cursor()
    id = input("New Student ID =")
    name = input("New Student Name =")
    age = input("New Student Age =")
    address = input("New Student Address =")
    email = input("New Student Email =")
    gpa = input("New Student GPA =")
    sql_insert_query = "insert into slist (ID, Name, Age, Address, Email, GPA) Value (%r, %r, %r, %r, %r, %r)" % (id,name,age,address,email,gpa)
    cursor.execute(sql_insert_query)
    ttdb.commit()
    print ("Adding successfully into slist table")
    Editting()
```

* **Purpose** – Inserts a new student record into `slist`.  
* **Step‑by‑step**  
  1. Creates a fresh cursor (`ttdb.cursor()`).  
  2. Prompts the user for each column value.  
  3. Builds an **unsafe** SQL string using Python’s `%r` formatting (prone to SQL injection).  
  4. Executes the query, commits the transaction.  
  5. Prints a success message and returns to the `Editting` submenu.

---

#### `Deleting()`

```python
def Deleting():
    cursor = ttdb.cursor()
    print ("Records before deleting single record from student table")
    sql_select_query = """select * from slist"""
    cursor.execute(sql_select_query)
    records = cursor.fetchall()
    for record in records :
        print (record)
    id = input("Delete from slist where ID = ")
    sql_Delete_query = "Delete from slist where ID = %s" % id    
    cursor.execute(sql_Delete_query)
    ttdb.commit()
    print ("\nStudent remove successfully ")
    print("\nTotal records from student table after remove single record\n ")
    cursor.execute(sql_select_query)
    records = cursor.fetchall()
    for record in records:
        print(record)
    Editting()
```

* **Purpose** – Deletes a single student row identified by `ID`.  
* **Key points**  
  - Shows the whole table **before** deletion.  
  - Builds a delete statement with `%s` substitution (still unsafe).  
  - Commits, then shows the table **after** deletion.  
  - Returns to `Editting`.

---

#### `Change()`

```python
def Change():
    Change = ttdb.cursor()
    print("Write Student ID need to change:")
    id = input()
    print("If you don't want to change please rewrite the same")
    print("Change student Name:")
    name = input()
    print("Change student Age:")
    age = input ()
    print("Change student Address:")
    address = input ()
    print("Change student Email:")
    email = input ()
    print("Change student GPA:")
    gpa = input ()
    Changing = "Update slist set Name = %r , Age = %r , Address = %r , Email = %r, GPA = %r where ID = %r " % (name,age,address,email,gpa,id)
    Change.execute(Changing)
    ttdb.commit()
    record = Change.fetchone()
    print(record)
    print("Change Success")
    Editting()
```

* **Purpose** – Updates all fields of a student row (identified by `ID`).  
* **Flow**  
  1. Opens a cursor (`Change`).  
  2. Prompts for the ID and the new values (user must re‑enter unchanged values if they don’t want a change).  
  3. Constructs an **UPDATE** statement using `%r` (again unsafe).  
  4. Executes, commits, then attempts to fetch a single row with `Change.fetchone()` (will return `None` because `UPDATE` does not produce a result set).  
  5. Prints a success message and goes back to `Editting`.

---

#### `Sort()`

```python
def Sort():
    print("""1:Sort by GPA.\n2:Sort by name.\n3:Return to mainmenu.""")    
    choice = input("Chosse next decision:")
    if choice == "1":
        GPAsort()
    elif choice == "2":
        namesort()
    elif choice == "3":
        menu()
    else:
        print("You must only select either 1 to 3.")
        print("Please try again.")
        Sort()
```

* **Purpose** – Sub‑menu for ordering the student list.  
* **Calls** – `GPAsort()`, `namesort()`, or returns to `menu()`.

---

#### `GPAsort()`

```python
def GPAsort():
   dtb = ttdb.cursor()
   change = "SELECT * FROM slist ORDER BY GPA DESC"
   dtb.execute(change)
   myresult = dtb.fetchall()
   for r in myresult:
      print(r)
   print("Done")
   Sort()
```

* **Purpose** – Retrieves all rows sorted by `GPA` descending and prints them.  
* **Flow** – After printing, returns to the `Sort` submenu.

---

#### `namesort()`

```python
def namesort():
   dtb = ttdb.cursor()
   change = "SELECT * FROM slist ORDER BY Name DESC"
   dtb.execute(change)
   myresult = dtb.fetchall()
   for r in myresult:
      print(r)
   print("Done")
   Sort()
```

* **Purpose** – Same as `GPAsort` but orders by `Name` descending.

---

#### `Alert()`

```python
def Alert():
    gmail_user = 'nguyendat4856@gmail.com'  
    gmail_password = 'dktahuio4856'

    sent_from = gmail_user  
    to = ('pubggodlike23@gmail.com')  
    subject = 'Alert Messange'  
    body = 'Hi! We send this to report your last exam GPA in lower than 5.5. Please spend time to study and learning to improve your skill. \n\n- Python'

    email_text = """\  
    From: %s  
    To: %s  
    Subject: %s

    %s
    """ % (sent_from, ", ".join(to), subject, body)

    try:  
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.sendmail(sent_from, to, email_text)
        server.close()

        print('Email sent!')
    except:  
        print('Something went wrong...')
        menu()
```

* **Purpose** – Sends a hard‑coded alert e‑mail via Gmail’s SMTP server.  
* **Key steps**  
  1. Sets sender credentials (plain text – **security risk**).  
  2. Builds a simple RFC‑822 style message (`email_text`).  
  3. Opens an SSL‑encrypted SMTP connection, logs in, sends the mail, and closes the connection.  
  4. On any exception, prints an error and returns to `menu()`.

---

#### `exit()`

```python
def exit():
    print(bye)
    sys.exit
```

* **Purpose** – Prints the farewell banner and terminates the program.  
* **Important note** – `sys.exit` is referenced **without parentheses**, so the interpreter does **not** actually exit. The function returns to the caller (normally `menu`) after printing `bye`. This is a bug.

---

#### `menu()` (called at the very end)

```python
menu()
```

* **Purpose** – Starts the interactive loop when the script is executed directly.

---

### 1.4 Execution Order (High‑level)

1. **Module import** → global variables (`ttdb`, `ttcursor`, `thongtin`, `listStd`, `bye`) are created.  
2. **`menu()`** is invoked → prints the main UI.  
3. User selects an option → control flows to one of the submenu functions (`Studentteam`, `Editting`, `Sort`, `Alert`, `exit`).  
4. Each submenu may call other helper functions (`List`, `Info`, `Adding`, `Deleting`, `Change`, `GPAsort`, `namesort`).  
5. After a helper finishes, it **always** returns to its parent submenu (or back to `menu`) by calling the parent function again.  
6. The program loops until the user chooses option **5** (calls `exit()`), which currently only prints the goodbye banner.

---  

## 2. Connections Between Functions  

| Caller | Callee | File | Relationship |
|--------|--------|------|--------------|
| `menu` | `Studentteam` | same | Main → Show/Info submenu |
| `menu` | `Editting` | same | Main → CRUD submenu |
| `menu` | `Sort` | same | Main → Sorting submenu |
| `menu` | `Alert` | same | Main → Email alert |
| `menu` | `exit` | same | Main → Termination |
| `Studentteam` | `List` | same | Sub‑menu → Print hard‑coded list |
| `Studentteam` | `Info` | same | Sub‑menu → Print DB rows (`thongtin`) |
| `Editting` | `Adding` | same | CRUD submenu → Insert |
| `Editting` | `Deleting` | same | CRUD submenu → Delete |
| `Editting` | `Change` | same | CRUD submenu → Update |
| `Sort` | `GPAsort` | same | Sorting submenu → Order by GPA |
| `Sort` | `namesort` | same | Sorting submenu → Order by Name |
| `GPAsort` / `namesort` | `Sort` | same | After printing, return to sorting menu |
| `Alert` | *none* (uses `smtplib`) | same | Sends e‑mail, no internal calls |
| `exit` | *none* (intended to call `sys.exit`) | same | Prints farewell banner |

> **No cross‑file dependencies** – the whole project lives in a single file.

---  

## 3. Overall Summary  

- The script is a **single‑file, procedural** student manager that demonstrates:
  - Connecting to a MySQL database (`mysql.connector`).
  - Performing **CRUD** operations with raw SQL strings.
  - Simple console UI using `print` and `input`.
  - Sending an e‑mail via Gmail’s SMTP server.

- **Strengths for learning**  
  - Shows how to open a DB connection, create cursors, execute queries, and commit changes.  
  - Illustrates a basic menu‑driven command‑line flow.  
  - Demonstrates use of the `smtplib` library for sending e‑mail.

- **Areas that need improvement (for a production‑ready project)**  
  1. **Security** – SQL statements are built with string interpolation (`%r` / `%s`). Use **parameterised queries** (`cursor.execute(sql, params)`) to avoid SQL injection.  
 