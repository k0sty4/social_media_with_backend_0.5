// A tiny dependency-free WYSIWYG editor.
//
// It's a `contentEditable` surface plus a toolbar that calls the classic
// `document.execCommand` API for bold / italic / underline / link / lists.
// `execCommand` is technically deprecated but still implemented in every
// browser and is by far the simplest way to get rich text without pulling in
// a heavy editor library. The HTML it produces is sent to the backend, which
// sanitises it against a strict tag whitelist before storing.

import { useRef, useEffect } from "react";
import { Box, IconButton, Divider, Tooltip } from "@mui/material";
import FormatBoldIcon from "@mui/icons-material/FormatBold";
import FormatItalicIcon from "@mui/icons-material/FormatItalic";
import FormatUnderlinedIcon from "@mui/icons-material/FormatUnderlined";
import InsertLinkIcon from "@mui/icons-material/InsertLink";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";

// Props:
//   value      — current HTML string (used to seed / externally reset content)
//   onChange   — called with the new HTML on every edit
//   placeholder — greyed-out hint shown while the editor is empty
export default function RichTextEditor({ value, onChange, placeholder = "Write something…", minHeight = 140 }) {
  const ref = useRef(null);

  // Sync content in from `value` only when the editor isn't focused — writing
  // to innerHTML while typing would reset the caret to the start on every key.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (document.activeElement !== el && el.innerHTML !== (value || "")) {
      el.innerHTML = value || "";
    }
  }, [value]);

  function emit() {
    onChange?.(ref.current?.innerHTML || "");
  }

  function exec(command, arg) {
    document.execCommand(command, false, arg);
    ref.current?.focus();
    emit();
  }

  function addLink() {
    const url = window.prompt("Link URL (https://…)");
    if (url && url.trim()) exec("createLink", url.trim());
  }

  // onMouseDown + preventDefault on each button keeps the text selection alive
  // so execCommand applies to the highlighted text, not nothing.
  const noBlur = (e) => e.preventDefault();

  return (
    <Box sx={{ border: 1, borderColor: "divider", borderRadius: 2, overflow: "hidden" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, px: 1, py: 0.5, bgcolor: "action.hover" }}>
        <Tooltip title="Bold">
          <IconButton size="small" onMouseDown={noBlur} onClick={() => exec("bold")}>
            <FormatBoldIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Italic">
          <IconButton size="small" onMouseDown={noBlur} onClick={() => exec("italic")}>
            <FormatItalicIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Underline">
          <IconButton size="small" onMouseDown={noBlur} onClick={() => exec("underline")}>
            <FormatUnderlinedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Bulleted list">
          <IconButton size="small" onMouseDown={noBlur} onClick={() => exec("insertUnorderedList")}>
            <FormatListBulletedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        <Tooltip title="Link">
          <IconButton size="small" onMouseDown={noBlur} onClick={addLink}>
            <InsertLinkIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
      <Box
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        onInput={emit}
        data-placeholder={placeholder}
        sx={{
          minHeight,
          px: 1.5,
          py: 1.25,
          outline: "none",
          fontSize: 14,
          lineHeight: 1.6,
          "& a": { color: "primary.main" },
          "&:empty:before": {
            content: "attr(data-placeholder)",
            color: "text.disabled",
          },
        }}
      />
    </Box>
  );
}
