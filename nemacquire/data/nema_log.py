# -*- coding: utf-8 -*-
# $Id: nema_log.py 1391 2018-03-07 18:55:43Z ram_raj $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.
#

from time import localtime, strftime


class LogCache():
    last_log_message = ""
    last_displayed_message = ""

def log(message, device_id = None, cache = None):
    m = strftime("%Y-%m-%d %H:%M:%S: ", localtime())
    if device_id:
        m += device_id + ': '
    m += message.rstrip()
    if cache:
        cache.last_log_message = message
        

    print m
