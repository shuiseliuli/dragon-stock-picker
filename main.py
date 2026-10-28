#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dragon Stock Picker - Main Entry Point
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
from scan_dragon_stocks import run_scanner

if __name__ == '__main__':
    run_scanner()
