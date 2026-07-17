"""复习流程 E2E 冒烟测试（无头浏览器，手机触屏模拟）。

改动复习页交互后、部署前跑一遍，防交互回归（如评分冒泡导致新卡自动翻面）。

用法（绝不直连生产，先起一次性实例）：
  1. 准备环境（chromium 已缓存在 ~/.cache/ms-playwright，venv 现建很快）：
       python3 -m venv /tmp/pwenv && /tmp/pwenv/bin/pip install playwright
       /tmp/pwenv/bin/playwright install chromium
  2. 用数据库副本起测试实例（端口 8399）：
       mkdir -p /tmp/mf-test && cp ~/memoflow/data/memoflow_v3.db /tmp/mf-test/ && chmod 777 /tmp/mf-test
       docker run -d --rm --name memoflow-test --user 1001:1001 -p 127.0.0.1:8399:8000 \
         --env-file ~/secrets/memoflow.env -e DATABASE_URL=sqlite:////data/memoflow_v3.db \
         -e STATIC_DIR=/app/static -v /tmp/mf-test:/data memoflow:v3
  3. 跑测试：
       source ~/secrets/memoflow.env && export AUTH_USERNAME AUTH_PASSWORD
       /tmp/pwenv/bin/python e2e/smoke_review.py
  4. 清理： docker stop memoflow-test && rm -rf /tmp/mf-test

断言：连续三张卡都是正面到达（不自动翻面）、点卡片任意处可翻面、
评分即切卡且三张各不相同（学习步卡让位给新卡）。
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get('MEMOFLOW_TEST_URL', 'http://127.0.0.1:8399')


def main() -> None:
    user = os.environ['AUTH_USERNAME']
    password = os.environ['AUTH_PASSWORD']
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={'width': 390, 'height': 844},
            has_touch=True, is_mobile=True,
        )
        page = ctx.new_page()
        page.goto(f'{BASE}/login', wait_until='networkidle')
        page.fill('input:not([type="password"])', user)
        page.fill('input[type="password"]', password)
        page.locator('button:has-text("登录")').tap()
        page.wait_for_selector('.review-card', timeout=10000)
        page.wait_for_timeout(800)

        seen = []
        for i in range(1, 4):
            front_btn = page.locator('.review-card-actions .btn-pill')
            assert front_btn.first.is_visible(), f'第{i}张卡不是正面到达（自动翻面回归！）'
            seen.append(page.locator('.review-question').first.inner_text()[:25])

            # 第2张点卡片本体验证 tap-anywhere，其余点按钮
            if i == 2:
                page.locator('.review-question').tap()
            else:
                front_btn.tap()
            page.wait_for_timeout(400)
            assert page.locator('.review-card-back-section').first.is_visible(), f'第{i}张卡点击后没翻面'

            page.locator('.review-rating-btn').filter(has_text='良').tap()
            page.wait_for_timeout(1000)

        assert len(set(seen)) == 3, f'卡片重复出现（学习步没让位给新卡）: {seen}'
        print('✓ 复习流程：正面到达 / 点击翻面 / 评分切卡 / 三张不重复')

        # 全页横向溢出审计：文档宽必须等于视口宽，否则手机会整页缩放
        for path in ['/', '/decks', '/articles', '/library', '/stats', '/import', '/settings']:
            page.goto(f'{BASE}{path}', wait_until='networkidle')
            page.wait_for_timeout(600)
            r = page.evaluate(
                '() => ({vw: document.documentElement.clientWidth, dw: document.documentElement.scrollWidth})'
            )
            assert r['dw'] <= r['vw'], f'{path} 横向溢出：文档宽 {r["dw"]} > 视口 {r["vw"]}'
        print('✓ 溢出审计：全部页面文档宽 == 视口宽')
        browser.close()


if __name__ == '__main__':
    try:
        main()
    except AssertionError as e:
        print(f'✗ {e}')
        sys.exit(1)
