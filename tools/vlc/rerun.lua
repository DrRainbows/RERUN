--[[
RERUN Guide - VLC extension.
Tunes channels inside the running VLC: same window, same position, no relaunch.

Install:  copy this file to  %APPDATA%\vlc\lua\extensions\rerun.lua
          (create the folders if missing), restart VLC.
Use:      VLC menu -> View -> RERUN Guide. Requires the RERUN server:
          python src/tune.py --serve
]]--

local SERVER = "http://localhost:8100"
local dlg = nil
local rows = {}

function descriptor()
    return {
        title = "RERUN Guide",
        version = "0.4",
        author = "RERUN",
        shortdesc = "RERUN Guide",
        description = "Tune RERUN channels inside VLC, joined in progress.",
        capabilities = {},
    }
end

function activate()
    build_dialog()
end

function deactivate()
    if dlg then dlg:delete() end
    dlg = nil
end

function close()
    deactivate()
end

function fetch_schedule()
    local s = vlc.stream(SERVER .. "/schedule.txt")
    if not s then return nil end
    local data = s:read(500000) or ""
    local out = {}
    for line in string.gmatch(data, "[^\n]+") do
        local num, name, now, offset, path =
            string.match(line, "^(%d+)|([^|]*)|([^|]*)|(%d+)|(.+)$")
        if num then
            table.insert(out, { num = num, name = name, now = now,
                                offset = tonumber(offset), path = path })
        end
    end
    return out
end

function tune_fn(ch)
    return function()
        local mrl = vlc.strings.make_uri(ch.path)
        pcall(function() vlc.playlist.clear() end)
        vlc.playlist.add({{ path = mrl, name = ch.num .. " " .. ch.name,
                            options = { ":start-time=" .. ch.offset } }})
    end
end

function build_dialog()
    if dlg then dlg:delete() end
    dlg = vlc.dialog("RERUN")
    local sched = fetch_schedule()
    if not sched or #sched == 0 then
        dlg:add_label("RERUN server not reachable.", 1, 1, 3, 1)
        dlg:add_label("Start it:  python src/tune.py --serve", 1, 2, 3, 1)
        dlg:add_button("Retry", build_dialog, 1, 3, 1, 1)
        return
    end
    dlg:add_label("<b>ON NOW</b>", 1, 1, 4, 1)
    local row = 2
    for _, ch in ipairs(sched) do
        dlg:add_button(ch.num .. "  " .. ch.name, tune_fn(ch), 1, row, 1, 1)
        local mins = math.floor(ch.offset / 60)
        dlg:add_label(ch.now .. "  (" .. mins .. "m in)", 2, row, 3, 1)
        row = row + 1
    end
    dlg:add_button("Refresh", build_dialog, 1, row, 1, 1)
end
