#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 14 16:31:02 2016

@author: richard
"""



import smtplib

#from email.Utils import formatdate
from email.mime.text import MIMEText
from email.MIMEMultipart import MIMEMultipart


# Set some variables
SMTPSERVER = "smtp.gmail.com"



class EmailNotify(object):
    def __init__(self, smtp_server = SMTPSERVER):
                     
        self.smtp_server = smtp_server
        self.message = MIMEMultipart()
        self.from_addr = None
        self.to_addr = None
        self.smtp = smtplib.SMTP(smtp_server,587,timeout=10)
        self.smtp_user = None
        self.smtp_pass = None
        
    def set_smtp_password(self,passwd):
        self.smtp_pass = passwd
        
        
    def set_to_address(self,addr):
        self.to_addr = addr
        self.message['To'] = addr
        
    def set_from_address(self,addr):
        self.from_addr = addr
        self.smtp_user = addr
        self.message['From'] = addr
        
    def set_subject(self,subject):
        self.message['Subject'] = subject
        
    def set_text_body(self,text):
        self.message.attach(MIMEText(text, 'plain'))
        
    def send_email(self):
        try:
            
            #s.set_debuglevel(0)
            self.smtp.ehlo()
            print "starting TLS\n" 
            self.smtp.starttls()
            self.smtp.ehlo()
            # Hash out below line if login is not needed
            print "Logging in to SMTP server\n"
            self.smtp.login(self.smtp_user, self.smtp_pass)
            #emailDate = formatdate(localtime=True)
                
            print self.message
            print "Trying to sendmail"
            self.smtp.sendmail(self.message['From'], self.message['To'], self.message.as_string())
            self.smtp.quit()
        except smtplib.SMTPException as error:
            print "Error: unable to send email :  {err}".format(err=error)
            
if __name__ == "__main__":
    from time import sleep
    
    while True:
        s = EmailNotify()
    
    
        s.set_smtp_password("G9TAR7qNzEjh")
        s.set_from_address("reynolds.avenue@clarke.biz")
        s.set_to_address("richard@clarke.biz")
        s.set_subject("Test Post")
        s.set_text_body("Hello")
        
        s.send_email()
        sleep(10)