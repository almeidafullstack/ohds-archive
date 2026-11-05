# Embedding on the Squarespace site

The archive is a full-page app, so it embeds as an iframe. Squarespace needs a
**Core plan or higher** for iframes inside a Code Block.

## Steps

1. Edit the page where the archive should appear.
2. Hover where you want it, click **+** (or *Add Block*), choose **Code**.
3. Open the block editor (pencil icon) and make sure **Type** is set to **HTML**
   and **Display Source** is switched **off**.
4. Delete the placeholder content and paste the snippet below.
5. Save, then **view the page logged out or in a private window** — Squarespace
   often hides embedded code from the logged-in editor. Use *Preview in Safe Mode*
   if the block looks blank while editing.

## The snippet

```html
<!-- Oregon Historic District — Photo Archives -->
<div class="ohd-archive-embed">
  <iframe
    src="https://discover.oregonhistoric.org/"
    title="Oregon Historic District photo archive: browse historic photos by address, street and year"
    loading="lazy"
    referrerpolicy="no-referrer-when-downgrade"
    allowfullscreen></iframe>
</div>

<style>
  .ohd-archive-embed {
    /* Tall enough that the map and the address list both breathe, but never
       taller than the window, so the page still scrolls normally around it. */
    position: relative;
    height: min(80vh, 820px);
    min-height: 520px;
    margin: 0 auto;
    border: 1px solid #d2d2d0;
    border-radius: 4px;
    overflow: hidden;
    background: #eceae4;
  }
  /* !important because Squarespace's Embed block pins iframes to its own
     16:9 box and would otherwise override this height. */
  .ohd-archive-embed iframe {
    position: absolute !important;
    inset: 0 !important;
    display: block;
    width: 100% !important;
    height: 100% !important;
    border: 0;
  }
  @media (max-width: 760px) {
    .ohd-archive-embed {
      height: min(78vh, 640px);
      min-height: 460px;
      /* Break out of Squarespace's side padding so the map gets the full width. */
      width: 100vw;
      margin-left: calc(50% - 50vw);
      border-left: 0;
      border-right: 0;
      border-radius: 0;
    }
  }
</style>
```

## Notes

- **Height is fixed, deliberately.** The widget fills whatever box it is given and
  scrolls its own sidebar, so it does not need to grow with its content. A
  cross-origin iframe cannot resize itself anyway without extra scripting.
- **Full-bleed on mobile** is the only opinionated bit: the negative margin pulls
  the frame past Squarespace's page gutter so the map is usable on a phone. Delete
  that block if you would rather it stay inside the normal content column.
- **Linking straight to one address** works by adding the hash, which is useful in a
  newsletter or a blog post:
  `https://discover.oregonhistoric.org/#a=22%20Brown%20St`
- **Nothing is tracked.** The widget loads no analytics, fonts, tiles or scripts from
  anywhere but its own folder, so it adds no third-party cookies to the page and
  needs no mention in a cookie banner.

## If it appears but is far too tall

The snippet went into an **Embed** block instead of a **Code** block. The Embed block
forces a 16:9 box and reserves that space even when the frame is the right height,
leaving a large gap below it. Delete it and paste the same snippet into a Code block.
In the Fluid Engine editor, drag the block's bottom edge up to fit the frame.

## If it does not appear

- Confirm the plan supports iframes (Core or higher).
- Check the page is not inside an Index section; code blocks can fail to render there.
- Log out and reload. Squarespace suppresses embeds for logged-in editors more often
  than people expect.
