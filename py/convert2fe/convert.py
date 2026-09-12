"""
convert.py

CLI wrapper - Tự động detect BMS/DSPF và chạy script chuyển đổi phù hợp.

Usage:
  # React only:
  python convert.py --input ./my_bms_folder --output ./output

  # React + Java Spring:
  python convert.py --input ./my_bms_folder --output ./output --spring ./spring_project --package com.example

Author: CICS2React
"""
import argparse
import subprocess
import sys
import os


def detect_type(input_folder):
    bms = [f for f in os.listdir(input_folder) if f.lower().endswith('.bms')]
    dspf = [f for f in os.listdir(input_folder) if f.lower().endswith('.dspf')]
    if bms and not dspf:
        return 'bms'
    if dspf and not bms:
        return 'dspf'
    if bms and dspf:
        print(f"[WARN] Found both .bms ({len(bms)}) and .dspf ({len(dspf)}) files. Specify --type explicitly.")
        return None
    print(f"[ERROR] No .bms or .dspf files found in: {input_folder}")
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Convert BMS/DSPF mainframe files to React + Java Spring code',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert BMS files to React only:
  python convert.py --input ./bms_src --output ./output/react

  # Convert DSPF files to React only:
  python convert.py --input ./dspf_src --output ./output/react --type dspf

  # Convert BMS files to React + Java Spring backend:
  python convert.py --input ./bms_src --output ./output/react --spring ./backend --package fa.training
        """
    )
    parser.add_argument('--input',    required=True,                      help='Folder chứa file BMS hoặc DSPF đầu vào')
    parser.add_argument('--output',   required=True,                      help='Folder output cho React components')
    parser.add_argument('--type',     choices=['bms', 'dspf'],            help='Loại file (tự động detect nếu không truyền)')
    parser.add_argument('--spring',                                        help='Folder Spring Boot project (tuỳ chọn, để sinh Java code)')
    parser.add_argument('--package',  default='fa.training',              help='Java package (mặc định: fa.training)')

    args = parser.parse_args()

    if not os.path.isdir(args.input):
        print(f"[ERROR] Folder input không tồn tại: {args.input}")
        sys.exit(1)

    file_type = args.type or detect_type(args.input)
    if not file_type:
        print("[ERROR] Không thể xác định loại file. Dùng --type bms hoặc --type dspf")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    type_flag = '-bms' if file_type == 'bms' else '-dspf'

    os.makedirs(args.output, exist_ok=True)

    if args.spring:
        script = 'bms2code.py' if file_type == 'bms' else 'dspf2code.py'
        cmd = [
            sys.executable, os.path.join(script_dir, script),
            type_flag, os.path.abspath(args.input),
            '-react', os.path.abspath(args.output),
            '-spring', os.path.abspath(args.spring),
            '-package', args.package,
        ]
    else:
        script = 'bms2react.py' if file_type == 'bms' else 'dspf2react.py'
        cmd = [
            sys.executable, os.path.join(script_dir, script),
            type_flag, os.path.abspath(args.input),
            '-react', os.path.abspath(args.output),
        ]

    print(f"[INFO] File type : {file_type.upper()}")
    print(f"[INFO] Input     : {os.path.abspath(args.input)}")
    print(f"[INFO] Output    : {os.path.abspath(args.output)}")
    if args.spring:
        print(f"[INFO] Spring    : {os.path.abspath(args.spring)}")
        print(f"[INFO] Package   : {args.package}")
    print(f"[INFO] Running   : {script}")
    print("-" * 50)

    result = subprocess.run(cmd, capture_output=False, text=True)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
