# -*- coding: utf-8 -*-
# $Id: acquired_data.py 1341 2018-01-30 18:10:46Z ram_raj $
#
# Copyright (c) 2016 NemaMetrix Inc. All rights reserved.
#

import os
from time import localtime, strftime

def get_new_full_filename(prefix, suffix, cfg):
    time_str= strftime("%Y-%m-%d_%H-%M-%S", localtime())
    fn = "%s_%s_w%s_%s.%s" % (prefix,
                              cfg.labnotes_items['strain'][2],
                              cfg.labnotes_items['worm_number'][2],
                              time_str,
                              suffix)
    full_fn = os.path.join(cfg.recording_folder, fn)
    return full_fn
