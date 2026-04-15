from flask import Flask, request, jsonify
import mysql.connector
from database_functions import create_new_user,db_login
from flask_cors import CORS
import json
app = Flask(__name__)
CORS(app)

# @app.route("/")
# def home():
#     return "API is running"

@app.route("/user/register",methods=["POST"])
def register():
    data=request.json
    create_new_user(data['name'],data['email'],data['password'])
    return jsonify({"message":"User Registered"})

@app.route("/login/",methods=["POST"])
def login():
    data=request.json
    user=db_login(data['email'],data['password'])
    if user:
        return jsonify({"message":"Login Successfull","data": user}), 200
    else:
        return jsonify({"message":"User not found!"}),  401
    


if __name__ == "__main__":
    app.run(debug=True)
