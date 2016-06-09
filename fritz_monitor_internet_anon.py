
# -*- coding: utf-8 -*-
"""
Created on Sat Feb 13 16:16:30 2016

@author: richard
"""
__version__ = '0.1.0'

import argparse
import datetime
import os
from fritzconnection import fritzstatus
from fritzconnection import fritztools
from emailAlert import EmailNotify
import cPickle as pickle

FRITZ_IP_ADDRESS = '192.168.1.1'
FRITZ_TCP_PORT = 49000

class FritzMonitorInternet(object):

    def __init__(self, master=None,
                       address=FRITZ_IP_ADDRESS,
                       port=FRITZ_TCP_PORT,
                       tx_alert_threshold_bytes=10000,
                       rx_alert_threshold_bytes=10000,
                       alert_interval=14400):
        
        self.status = fritzstatus.FritzStatus(address=address, port=port)
        self.max_upstream, self.max_downstream = self.status.max_byte_rate
        self.emailAlert = EmailNotify()
        self.emailAlert.set_smtp_password("XXXXXXXXX")
        self.emailAlert.set_from_address("reynolds.avenue@clarke.biz")
        self.emailAlert.set_to_address("richard@clarke.biz")
        self.emailAlert.set_subject("FritzBox: Internet Alert!")
       
        self.last_date_and_time = None
        self.last_fritzbox_traffic_counter_rx_32bit = None
        self.last_fritzbox_traffic_counter_tx_32bit = None
        self.fritzbox_traffic_counter_rx_32bit = self.status.bytes_received
        self.fritzbox_traffic_counter_tx_32bit = self.status.bytes_sent
        
        self.fritzbox_traffic_counter_at_last_alert_interval_tx = None
        self.fritzbox_traffic_counter_at_last_alert_interval_rx = None
        self.date_and_time = datetime.datetime.now()
        
        self.delta_tx = 0
        self.delta_rx = 0
        self.fritzbox_traffic_counter_at_this_alert_interval_tx = 0 #Actually need to read this from an external persistent file
        self.fritzbox_traffic_counter_at_this_alert_interval_rx = 0 #Actually need to read this from an external persistent file
        #These variables are used to store the FritzBox receive and transmit data counters as
        #they were at the start of the ISP billing cycle.
        self.billing_interval_ref_tx = 0 #Will be read from persistent file
        self.billing_interval_ref_rx = 0
        self.timer_count = 0
        self.alert_interval_seconds = alert_interval
        self.tx_alert_threshold = float(tx_alert_threshold_bytes)
        self.rx_alert_threshold = float(rx_alert_threshold_bytes)
        self.read_last_traffic_count_from_file()
        
    def set_alert_parameters(self, tx_alert_threshold_bytes = 2e9, rx_alert_threshold_bytes = 4e9):
        #self.alert_window_length_seconds = window_length
        self.tx_alert_threshold = tx_alert_threshold_bytes
        self.rx_alert_threshold = rx_alert_threshold_bytes
        
    def print_parameters(self):
        delta_received = fritztools.format_num(self.delta_rx)
        delta_sent = fritztools.format_num(self.delta_tx)
        
        tx_thresh = fritztools.format_num(self.tx_alert_threshold)
        rx_thresh = fritztools.format_num(self.rx_alert_threshold)
        rx_billing_delta = fritztools.format_num(self.fritzbox_traffic_counter_rx_32bit-self.billing_interval_ref_rx)
        tx_billing_delta = fritztools.format_num(self.fritzbox_traffic_counter_tx_32bit-self.billing_interval_ref_tx )
        alertText = 'Time since last check: {}\n\n'.format(self.delta_time.seconds)
        alertText += 'Alert Interval = {}\n\n'.format(self.alert_interval_seconds)
        alertText += 'Alert Threshold TX/RX = %s/%s\n\n' % (tx_thresh,rx_thresh)
        alertText += 'Timer Count = {}\n\n'.format(self.timer_count)
        alertText += 'FritzBox register bytes_received: {}\n\n'.format(self.status.bytes_received)
        alertText += 'FritzBox register bytes_sent: {}\n\n'.format(self.status.bytes_sent)
        alertText += 'During the last monitor interval %s have been received and %s has been transmitted\n\n' % (delta_received,delta_sent)
        #alertText += 'Total data sent: %s bytes\t Total data received = %s bytes\n\n' % (self.cummulative_tx,self.cummulative_rx)
        #alertText += 'Total data sent: %s\t Total data received = %s\n\n' % (total_sent,total_received)
        alertText += 'Billing Interval Start Values: Tx = {}\t Rx = {}\n\n'.format(self.billing_interval_ref_tx,self.billing_interval_ref_rx)
        alertText += 'Since start of billing interval : Data Sent = %s\t Data Received = %s' %(tx_billing_delta,rx_billing_delta)
        print alertText
  
    def set_tx_threshold(self,threshold_bytes):
        self.tx_alert_threshold = threshold_bytes
        
    def set_rx_threshold(self,threshold_bytes):
        self.rx_alert_threshold = threshold_bytes
             
    def calculate_traffic_delta(self):
        self.read_last_traffic_count_from_file()
        #self.fritzbox_traffic_counter_rx_32bit = self.status.bytes_received
        #self.fritzbox_traffic_counter_tx_32bit = self.status.bytes_sent
        self.date_and_time = datetime.datetime.now()
        
        self.delta_rx = self.fritzbox_traffic_counter_rx_32bit - self.last_fritzbox_traffic_counter_rx_32bit
        #Check to see if the 32 bit traffic counter in Fritzbox has wrapped and compensate
        if self.delta_rx < 0:
            self.delta_rx = self.delta_rx + pow(2,32)
            
        self.delta_tx = self.fritzbox_traffic_counter_tx_32bit - self.last_fritzbox_traffic_counter_tx_32bit
        #Check to see if the 32 bit traffic counter in Fritzbox has wrapped and compensate
        if self.delta_tx < 0:
            self.delta_tx = self.delta_tx + pow(2,32)
            
        self.delta_time = self.date_and_time - self.last_date_and_time
        
        self.timer_count += self.delta_time.seconds
        
       
        #Internet plan data rollover date/time
        if self.date_and_time.day == 17:
            if ( (self.date_and_time.hour > 18) and (self.date_and_time.hour < 19) ):
                rx_billing_delta = fritztools.format_num(self.fritzbox_traffic_counter_rx_32bit-self.billing_interval_ref_rx)
                tx_billing_delta = fritztools.format_num(self.fritzbox_traffic_counter_tx_32bit-self.billing_interval_ref_tx )
                
                self.billing_interval_ref_tx = self.fritzbox_traffic_counter_tx_32bit
                self.billing_interval_ref_rx = self.fritzbox_traffic_counter_rx_32bit
                alertText = 'Internet Account Billing Rollover\n\n'
                alertText += 'Billing Interval Start Values: Tx = {}\t Rx = {}\n\n'.format(self.billing_interval_ref_tx,self.billing_interval_ref_rx)
                alertText += 'Total data during last billing interval : Data Sent = %s\t Data Received = %s' %(tx_billing_delta,rx_billing_delta)
                self.emailAlert.set_text_body(alertText)
                self.emailAlert.send_email()
        
        
        
        #text = "elapsed time: %d seconds, delta received: %d, delta sent: %s\n" % (self.delta_time.seconds,self.delta_rx, self.delta_tx)
        #print text
        #print "timer_count = %d\n" % self.timer_count
        #print "alert_interval_seconds = %d\n" % self.alert_interval_seconds
	
        
        if self.timer_count >= self.alert_interval_seconds:
            self.fritzbox_traffic_counter_at_this_alert_interval_tx = self.fritzbox_traffic_counter_tx_32bit
            self.fritzbox_traffic_counter_at_this_alert_interval_rx = self.fritzbox_traffic_counter_rx_32bit
            
            self.delta_rx = self.fritzbox_traffic_counter_at_this_alert_interval_rx - self.fritzbox_traffic_counter_at_last_alert_interval_rx
            self.delta_tx = self.fritzbox_traffic_counter_at_this_alert_interval_tx - self.fritzbox_traffic_counter_at_last_alert_interval_tx
            self.timer_count = 0
            
        
            if ( (self.delta_rx > self.rx_alert_threshold) or (self.delta_tx > self.tx_alert_threshold) ):
                print 'Alert triggered'
                alert_interval_rx = fritztools.format_num(self.delta_rx)
                alert_interval_tx = fritztools.format_num(self.delta_tx)
                
                rx_billing_delta = fritztools.format_num(self.fritzbox_traffic_counter_rx_32bit-self.billing_interval_ref_rx)
                tx_billing_delta = fritztools.format_num(self.fritzbox_traffic_counter_tx_32bit-self.billing_interval_ref_tx )
                alertText = 'Time since last check: {}\n\n'.format(self.delta_time)
                alertText += 'During the last alert monitor interval %s have been received and %s has been transmitted\n\n' % (alert_interval_rx,alert_interval_tx)
                
                
                alertText += 'Billing Interval Start Values: Tx = {}\t Rx = {}\n\n'.format(self.billing_interval_ref_rx,self.billing_interval_ref_rx)
                alertText += 'Since start of billing interval : Data Sent = %s\t Data Received = %s\n' %(tx_billing_delta,rx_billing_delta)
                
                self.emailAlert.set_text_body(alertText)
                self.emailAlert.send_email()
            
        self.write_current_traffic_count_to_file()
        self.print_parameters()
            
    def write_current_traffic_count_to_file(self):        
        f = open("internet_traffic.pickle","w") #opens file with name of "test.txt"
        pickle.dump([self.date_and_time, self.timer_count, self.fritzbox_traffic_counter_rx_32bit, self.fritzbox_traffic_counter_tx_32bit, self.fritzbox_traffic_counter_at_this_alert_interval_rx, self.fritzbox_traffic_counter_at_this_alert_interval_tx, self.billing_interval_ref_rx, self.billing_interval_ref_tx], f)
        f.close()
        
    def read_last_traffic_count_from_file(self):
        if os.path.isfile("./internet_traffic.pickle"):
            with open("internet_traffic.pickle","r") as f:
                data = pickle.load(f)
                self.last_date_and_time = data[0]
                self.timer_count = data[1]
                self.last_fritzbox_traffic_counter_rx_32bit = data[2]
                self.last_fritzbox_traffic_counter_tx_32bit = data[3]
                self.fritzbox_traffic_counter_at_last_alert_interval_rx = data[4]
                self.fritzbox_traffic_counter_at_last_alert_interval_tx = data[5]
                self.billing_interval_ref_rx = data[6]
                self.billing_interval_ref_tx = data[7]
                f.close()
#                print 'last_date_and_time = {}'.format(self.last_date_and_time)
#                print 'last_fritzbox_traffic_counter_rx = {}'.format(self.last_fritzbox_traffic_counter_rx_32bit)
#                print 'last_fritzbox_traffic_counter_tx = {}'.format(self.last_fritzbox_traffic_counter_tx_32bit)
#                print 'cummulative rx = {}'.format(self.cummulative_rx)
#                print 'cummulative tx = {}'.format(self.cummulative_tx)
#                print 'Billing Interval Start Rx = {}'.format(self.billing_interval_ref_rx)
#                print 'Billing Interval Start Tx = {}'.format(self.billing_interval_ref_tx)
        else:
            #May be first time the script has run so no previous record
            print 'internet_traffic.pickle file did not exist'
            self.last_date_and_time = self.date_and_time
            self.timer_count = 0
            self.last_fritzbox_traffic_counter_rx_32bit = self.status.bytes_received
            self.last_fritzbox_traffic_counter_tx_32bit = self.status.bytes_sent
            self.billing_interval_ref_tx = self.status.bytes_sent
            self.billing_interval_ref_rx = self.status.bytes_received
            
# ---------------------------------------------------------
# cli-section:
# ---------------------------------------------------------

def _get_cli_arguments():
    parser = argparse.ArgumentParser(description='FritzBox Monitor')
    parser.add_argument('-i', '--ip-address',
                        nargs='?', default=FRITZ_IP_ADDRESS,
                        dest='address',
                        help='ip-address of the FritzBox to connect to. '
                             'Default: %s' % FRITZ_IP_ADDRESS)
    parser.add_argument('-p', '--port',
                        nargs='?', default=FRITZ_TCP_PORT,
                        dest='port',
                        help='port of the FritzBox to connect to. '
                             'Default: %s' % FRITZ_TCP_PORT)
                             
    parser.add_argument('-s', '--send-thresh',
                        nargs='?', default=50000,
                        dest='tx_threshold',
                        help='Send traffic alert threshold '
                             'Default: %d' % 2e9)  
                             
    parser.add_argument('-r', '--receive-thresh',
                        nargs='?', default=50000,
                        dest='rx_threshold',
                        help='Receive traffic alert threshold '
                             'Default: %d' % 4e9)                          
     
    parser.add_argument('-t', '--alert-interval',
                            nargs='?', default=14400,
                            dest='alert_interval',
                            help='Traffic alerts window measurement interval '
                                 'Default: %d' % 14400)                                  
    args = parser.parse_args()
    return args
    
if __name__ == '__main__':
    #root_dir = '/media/files/files/Seafile/Development/ShellScripts/checkFritzBox'
    
    arguments = _get_cli_arguments()
    print os.getcwd()
    #os.chdir(root_dir)
    print os.getcwd()
    app = FritzMonitorInternet(address=arguments.address, port=arguments.port, tx_alert_threshold_bytes=arguments.tx_threshold, rx_alert_threshold_bytes=arguments.rx_threshold, alert_interval=int(arguments.alert_interval))
    
    #app.set_alert_parameters(tx_alert_threshold_bytes = 50000, rx_alert_threshold_bytes = 100000)
    app.calculate_traffic_delta()
    
