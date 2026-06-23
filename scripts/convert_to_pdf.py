#!/usr/bin/env python3
"""
proposal.pptx → proposal.pdf 일괄 변환 (Microsoft PowerPoint 앱 사용)

사용법:
    python scripts/convert_to_pdf.py             # dry-run
    python scripts/convert_to_pdf.py --apply     # 실제 변환
    python scripts/convert_to_pdf.py --apply --verbose
"""

import subprocess
import argparse
import time
import threading
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PROJECTS_DIR = BASE_DIR / "data" / "projects"


# ── AppleScript 헬퍼 ──────────────────────────────────────────────────────────

def _run(script: str, timeout: int = 10) -> str:
    """AppleScript 실행 후 stdout 반환. 실패/타임아웃 시 빈 문자열."""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return ""


def _open_in_thread(src: Path):
    """open 명령은 글꼴 대화상자가 있으면 블로킹되므로 스레드에서 실행"""
    _run(f'tell application "Microsoft PowerPoint" to open POSIX file "{src}"', timeout=120)


def _activate_ppt():
    _run('tell application "Microsoft PowerPoint" to activate', timeout=5)


def _close_all_presentations():
    """이전 실행에서 열린 채 남은 파일 정리"""
    _run("""
tell application "Microsoft PowerPoint"
    try
        close every presentation saving no
    end try
end tell
""", timeout=10)


def _try_dismiss_once() -> str:
    """
    대화상자(sheet) 버튼 클릭을 한 번 시도한다.
    반환값: 'clicked', 'open', 'none' 중 하나
    """
    script = """
tell application "System Events"
    tell process "Microsoft PowerPoint"
        try
            if (count of windows) < 1 then return "none"
            set theWin to window 1
            -- sheet(창에 붙은 대화상자) 확인
            try
                if (count of sheets of theWin) > 0 then
                    set theSheet to sheet 1 of theWin
                    -- 버튼 이름 순서대로 시도
                    set btnNames to {"제한된 글꼴 제거", "대체 글꼴 사용", "확인", "OK", "예", "Yes"}
                    repeat with bName in btnNames
                        try
                            click button bName of theSheet
                            return "clicked"
                        end try
                    end repeat
                    -- 이름 매칭 실패 시 첫 번째 버튼
                    try
                        click button 1 of theSheet
                        return "clicked"
                    end try
                end if
            end try
        end try
    end tell
end tell
-- 대화상자 없이 이미 열린 경우
tell application "Microsoft PowerPoint"
    try
        if (count of presentations) > 0 then return "open"
    end try
end tell
return "none"
"""
    return _run(script, timeout=8)


def _presentation_is_open() -> bool:
    result = _run("""
tell application "Microsoft PowerPoint"
    try
        if (count of presentations) > 0 then return "yes"
    end try
end tell
return "no"
""", timeout=8)
    return result == "yes"


def _save_pdf(dst: Path) -> tuple[bool, str]:
    script = f"""
tell application "Microsoft PowerPoint"
    set theDoc to active presentation
    save theDoc in POSIX file "{dst}" as save as PDF
    close theDoc saving no
end tell
"""
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return False, r.stderr.strip()
    return True, ""


# ── 변환 메인 로직 ────────────────────────────────────────────────────────────

def convert(src: Path, dst: Path, verbose: bool) -> bool:
    # 1. PowerPoint 활성화 후 파일 열기 (블로킹이므로 스레드에서 실행)
    _activate_ppt()
    t = threading.Thread(target=_open_in_thread, args=(src,), daemon=True)
    t.start()

    # 2. 글꼴 대화상자가 나타나면 클릭 (Python 루프 + 단발성 AppleScript)
    dialog_result = "none"
    for i in range(35):                 # 최대 35초 대기
        time.sleep(1)
        result = _try_dismiss_once()
        if result == "clicked":
            dialog_result = f"clicked (after {i+1}s)"
            if verbose:
                print(f"       대화상자 클릭 ({i+1}초)")
            break
        if result == "open":
            dialog_result = "no-dialog"
            break

    # 3. 파일이 완전히 열릴 때까지 대기 (최대 15초 추가)
    for _ in range(15):
        if _presentation_is_open():
            break
        time.sleep(1)
    else:
        print("  ❌ 파일 열기 실패 (타임아웃)")
        t.join(timeout=3)
        return False

    time.sleep(1)

    # 4. PDF 저장
    ok, err = _save_pdf(dst)
    t.join(timeout=5)

    if not ok:
        print(f"  ❌ PDF 저장 실패: {err}")
        return False
    if not dst.exists():
        print("  ❌ 출력 파일 없음")
        return False

    if verbose:
        size_kb = dst.stat().st_size // 1024
        print(f"  ✅ {dst.name} ({size_kb} KB)  [{dialog_result}]")
    return True


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="proposal.pptx → proposal.pdf 일괄 변환")
    parser.add_argument("--apply", action="store_true", help="실제 변환 실행 (기본: dry-run)")
    parser.add_argument("--verbose", action="store_true", help="상세 출력")
    args = parser.parse_args()

    targets = sorted(PROJECTS_DIR.glob("*/proposal.pptx"))
    if not targets:
        print("변환할 proposal.pptx 파일이 없습니다.")
        return

    mode = "🟢 [APPLY]" if args.apply else "🔵 [DRY-RUN]"
    print(f"\n{mode} 변환 대상: {len(targets)}개\n")

    if args.apply:
        _close_all_presentations()

    ok = fail = skip = 0

    for pptx in targets:
        pdf = pptx.with_name("proposal.pdf")
        project = pptx.parent.name

        if pdf.exists():
            print(f"  ⏭️  {project}  (이미 존재)")
            skip += 1
            continue

        print(f"  📄 {project}")

        if not args.apply:
            print(f"       → proposal.pdf 로 변환 예정")
            ok += 1
            continue

        success = convert(pptx, pdf, args.verbose)
        if success:
            ok += 1
        else:
            fail += 1

        time.sleep(1)   # 파일 간 간격

    print()
    if args.apply:
        print(f"✅ 완료  성공: {ok}  실패: {fail}  건너뜀: {skip}")
    else:
        print(f"💡 실제 변환: python scripts/convert_to_pdf.py --apply")
        print(f"   대상 {ok}개 / 이미 존재 {skip}개")


if __name__ == "__main__":
    main()
