"""Navigate the presentation Details drawer before exercising an existing control."""


async def ui_action(page, selector, method='click', *args):
    locator = page.locator(selector)
    inside = await locator.evaluate("element => Boolean(element.closest('#technical-details'))")
    opened = await page.locator('#technical-details').evaluate('dialog => dialog.open')
    if inside and not opened:
        await page.locator('#details-button').click()
    elif not inside and opened:
        await page.locator('#close-details').click()
    if inside:
        collapsed = await locator.evaluate("""element => {
          const settings = element.closest('.settings-card');
          return Boolean(settings && !settings.open && element !== settings.querySelector(':scope > summary'));
        }""")
        if collapsed:
            await page.locator('.settings-card > summary').click()
    return await getattr(locator, method)(*args)
