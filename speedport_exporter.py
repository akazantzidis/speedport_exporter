import flask
import requests
import argparse
from tabulate import tabulate
import json
from flask import Flask
import datetime
from prometheus_client import make_wsgi_app, Gauge ,Enum
import urllib3
import os

urllib3.disable_warnings()

def get_speedport_data(arg,ip):
    lall = []
    lwlan = []
    ldsl = []
    d = {}
    all,wlan,dsl = False,False,False
    if arg == 'ALL':
        all = True
    elif arg == 'WLAN':
        wlan = True
    elif arg == 'DSL':
        dsl = True
    else:
        print("| ERROR | \"Check argument provided at get_speedport_data()\" | \"Input\":\"{}\" |".format(arg))
        exit(1)

    url = "https://"+ip+"/data/Status.json"
    headers = {'Accept-Language' : 'en'}
    try :
        r = requests.get(url, headers=headers,verify=False)
    except RuntimeError as e:
        print('Errors happened during execution:\n{}'.format(e))
        exit(1)

    for item in r.json():
        id = item['varid']
        val =  item['varvalue']
        d[id] = val
        lall.append([id,val])

    if all :
        return lall,d
    if wlan :
        dl = {}
        for item in lall:
            if 'wlan' in item[0] or 'wps' in item[0]:
                lwlan.append(item)
                dl[item[0]] = item[1] 
        return lwlan,dl
    if dsl :
        dd = {}
        for item in lall:
            if 'dsl' in item[0]:
                ldsl.append(item)
                dd[item[0]] = item[1]
        return ldsl,dd

def run_http(arg,listen_host,listen_port):

    vdsl_atnd = Gauge('vdsl_atn_download', 'VDSL link download attenuation dB')
    vdsl_atnu = Gauge('vdsl_atn_upload', 'VDSL link upload attenuation dB')
    dsl_crc_err = Gauge('dsl_crc_errors', 'VDSL link CRC errors')
    dsl_downstream = Gauge('dsl_downstream', 'VDSL line download speed kBits/s') 
    dsl_fec_err = Gauge('dsl_fec_errors', 'VDSL link FEC errors')
    dsl_link_status = Enum('dsl_link_status', 'VDSL link status',states=['online','offline'])
    dsl_max_downstream = Gauge('dsl_max_downstream', 'VDSL line max attenable download speed kBit/s') 
    dsl_max_upstream = Gauge('dsl_max_upstream', 'VDSL line max attenable upload speed kBit/s')
    dsl_snr_download = Gauge('dsl_snr_downstream', 'VDSL line SNR downstream dB')
    dsl_snr_upload = Gauge('dsl_snr_upstream', 'VDSL line SNR upstream dB')   
    dsl_upstream = Gauge('dsl_upstream', 'VDSL line upload speed kBit/s')

    app = Flask(__name__)
    @app.route('/')
    def ret_data():
        app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
        data = get_speedport_data(arg,ip)
        return flask.jsonify(data[1])
    
    @app.route('/metrics',)
    def metrics():
        data = get_speedport_data('ALL',ip)
        if data == '':
            atnd ,atnu ,crc ,dsld = 0,0,0,0
            fec ,status ,dslmxd, dslmxu = 0,0,0,0
            snrd ,snru ,dslu = 0,0,0 
        else:
            atnd ,atnu ,crc ,dsld = data[1]['vdsl_atnd'],data[1]['vdsl_atnu'],data[1]['dsl_crc_errors'],data[1]['dsl_downstream']
            fec ,status ,dslmxd, dslmxu = data[1]['dsl_fec_errors'],data[1]['dsl_status'],data[1]['dsl_max_downstream'],data[1]['dsl_max_upstream']
            snrd ,snru ,dslu = data[1]['dsl_snr'].split('/')[0].strip(),data[1]['dsl_snr'].split('/')[1].strip(),data[1]['dsl_upstream']

        vdsl_atnd.set(atnd) 
        vdsl_atnu.set(atnu)
        dsl_crc_err.set(crc)
        dsl_downstream.set(dsld)
        dsl_fec_err.set(fec)
        dsl_link_status.state(status)
        dsl_max_downstream.set(dslmxd)
        dsl_max_upstream.set(dslmxu)
        dsl_snr_download.set(snrd)
        dsl_snr_upload.set(snru)
        dsl_upstream.set(dslu)
        
        return make_wsgi_app()

    app.run(threaded=True,host=listen_host,port=listen_port)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--DSL','-d',action="store_true")
    parser.add_argument('--WLAN','-w',action="store_true")
    parser.add_argument('--all','-a',action="store_true")
    parser.add_argument('--table','-t',action="store_true")
    parser.add_argument('--http',action="store_true")
    parser.add_argument('--speedport_ip',nargs="?", default='192.168.1.1')
    parser.add_argument('--listen_port',nargs="?", default='8080')
    parser.add_argument('--listen_ip',nargs="?",default='localhost')
    args = parser.parse_args()
    
    if 'SPEEDPORT_IP' in os.environ:
        ip = os.environ['SPEEDPORT_IP']
    else:
        ip = args.speedport_ip
    
    if 'SPEEDPORT_EXPORTER_LISTEN_PORT' in os.environ:
        lp = os.environ['SPEEDPORT_EXPORTER_LISTEN_PORT']
    else:
        lp = args.listen_port

    if 'SPEEDPORT_EXPORTER_LISTEN_IP' in os.environ:
        lip = os.environ['SPEEDPORT_EXPORTER_LISTEN_IP']
    else:
        lip = args.listen_ip
        
    if args.DSL:
        passarg = 'DSL'
    elif args.WLAN:
        passarg = 'WLAN'
    else:
        passarg = 'ALL'

    data = get_speedport_data(passarg,ip)
    if args.http is False and args.table is True:
        exit(print(tabulate(data[0], tablefmt="grid")))
    elif args.http is False and args.table is False:
        exit(print(json.dumps(data[1])))
    elif args.http:
        exit(run_http(passarg,lip,lp))
