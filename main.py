import tkinter as tk                              # tkinter is the standard Python GUI library; 'tk' alias is the convention
from tkinter import ttk, font                    # ttk provides themed widgets (Scrollbar); font module not directly used but kept for extension
import json                                      # used to read/write the JSON save file
import os                                        # used to check whether the save file exists before trying to open it
from dataclasses import dataclass, asdict, field # dataclass decorator auto-generates __init__; asdict converts to dict; field lets us set default factories
from datetime import datetime                    # used to record the creation timestamp and to parse/format it for display


# ── Dataclass ──────────────────────────────────────────────────────────────────

@dataclass                                       # decorator that auto-generates __init__, __repr__, __eq__ from the fields below
class TodoItem:
    name: str                                    # the task text entered by the user
    created_at: str = field(                     # ISO-8601 timestamp string; default_factory means each instance gets its own timestamp at creation time
        default_factory=lambda: datetime.now().isoformat()
    )
    completed: bool = False                      # tracks whether the task has been checked off; False by default
    position: int = 0                            # integer that records the card's order in the list; updated on every save

    @staticmethod
    def from_dict(d: dict) -> "TodoItem":        # static method so we can call TodoItem.from_dict(...) without an existing instance
        return TodoItem(                         # reconstructs a TodoItem from a plain dict loaded out of JSON
            name=d["name"],                      # pull the task text back out of the dict
            created_at=d["created_at"],          # restore the original creation timestamp
            completed=d["completed"],            # restore the completed flag
            position=d["position"],              # restore the saved position so we can sort on load
        )

    def to_dict(self) -> dict:                   # converts this dataclass instance to a plain dict for JSON serialisation
        return asdict(self)                      # asdict() recursively converts all dataclass fields to a dict

    def display_created(self) -> str:            # returns a human-readable creation time string for display on the card
        try:
            dt = datetime.fromisoformat(self.created_at)   # parse the ISO string back into a datetime object
            return dt.strftime("%d %b %Y  %H:%M")          # format as e.g. "22 Mar 2026  14:35"
        except ValueError:                       # if the stored string is malformed, just return it raw rather than crashing
            return self.created_at


# ── Persistence ────────────────────────────────────────────────────────────────

SAVE_FILE = "todo_list.json"                     # name of the JSON file written to the working directory


def load_todos() -> list[TodoItem]:              # reads the JSON file and returns a sorted list of TodoItem objects
    if os.path.exists(SAVE_FILE):                # only try to open the file if it actually exists (avoids FileNotFoundError on first run)
        with open(SAVE_FILE, "r", encoding="utf-8") as f:   # open in read mode with explicit UTF-8 so special characters survive
            data = json.load(f)                  # parse the JSON array into a list of plain Python dicts
        items = [TodoItem.from_dict(d) for d in data]       # convert each dict back into a TodoItem dataclass instance
        items.sort(key=lambda t: t.position)     # sort by saved position so the list order is restored correctly
        return items                             # hand the sorted list back to the caller
    return []                                    # if no file exists yet, start with an empty list


def save_todos(todos: list[TodoItem]) -> None:   # writes the current list to disk, re-assigning position numbers first
    for i, item in enumerate(todos):             # walk through the list with an index so we can update each item's position
        item.position = i                        # overwrite position with the item's current index — keeps positions contiguous after drags/deletes
    with open(SAVE_FILE, "w", encoding="utf-8") as f:       # open (or create) the file in write mode; overwrites any previous content
        json.dump(                               # serialise the list to JSON
            [t.to_dict() for t in todos],        # convert every TodoItem to a plain dict first, since json.dump can't handle dataclasses directly
            f,                                   # write into the open file handle
            indent=2,                            # pretty-print with 2-space indentation so the file is human-readable
        )


# ── Palette & constants ────────────────────────────────────────────────────────

BG          = "#1a1a2e"   # deep navy — main window background
CARD_BG     = "#16213e"   # slightly lighter navy — default card background
CARD_HOVER  = "#1a2a4a"   # even lighter — card background when mouse hovers over it
ACCENT      = "#e94560"   # vivid red-pink — accent bar, checkbox, add button
ACCENT2     = "#0f3460"   # dark blue — checkbox fill colour when ticked
TEXT        = "#eaeaea"   # near-white — primary text on cards
SUBTEXT     = "#7a8ba0"   # muted blue-grey — secondary text (timestamps, drag handle, delete button)
DONE_TEXT   = "#4a5a6a"   # darker grey — task name text when the task is completed
DONE_CARD   = "#111827"   # very dark — card background for completed tasks
ENTRY_BG    = "#0f3460"   # dark blue — background of the text entry field
BORDER      = "#0f3460"   # same dark blue — the 1-pixel separator line under the entry row
DRAG_LINE   = "#e94560"   # same red-pink as ACCENT — the drop-target indicator line shown during drag

CARD_PAD_Y  = 6           # pixels of vertical gap between cards; also used in drag index calculation
CARD_HEIGHT = 78          # approximate rendered card height in pixels; used to convert cursor Y position into a list index during drag


# ── TodoApp ────────────────────────────────────────────────────────────────────

class TodoApp:
    def __init__(self, root: tk.Tk):              # constructor receives the root Tk window created in main()
        self.root = root                          # store reference so other methods can access the window
        self.root.title("Steele's Todo List")     # text shown in the window's title bar
        self.root.geometry("760x680")             # initial window size in pixels (width x height)
        self.root.configure(bg=BG)               # set the window background to the dark navy palette colour
        self.root.resizable(True, True)           # allow the user to resize the window both horizontally and vertically

        self.todos: list[TodoItem] = load_todos() # load any previously saved tasks from disk; empty list if no file exists

        # drag state — these four attributes track what is happening during a drag-and-drop operation
        self._drag_source: int | None = None      # list index of the card currently being dragged; None when no drag is active
        self._drag_ghost: tk.Toplevel | None = None   # the semi-transparent floating window that follows the cursor during a drag
        self._drop_line: tk.Frame | None = None   # reference kept for potential future use; the actual line is re-created each render
        self._drop_index: int | None = None       # the list index where the card would be inserted if the user releases the mouse now

        self._build_ui()                          # create and lay out all the tkinter widgets
        self._render_list()                       # populate the card list with the loaded tasks

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)  # intercept the window-close button so we can save before exiting

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── header ──
        header = tk.Frame(self.root, bg=BG)       # invisible container frame for the title + counter label
        header.pack(fill=tk.X, padx=24, pady=(28, 0))  # stretch across full width; 28px top padding, no bottom padding

        tk.Label(                                 # the "✦ TODO" title label
            header, text="✦ TODO", bg=BG, fg=ACCENT,
            font=("Georgia", 28, "bold"),         # Georgia gives a slightly editorial feel at large size
        ).pack(side=tk.LEFT)                      # anchor to the left side of the header frame

        self._count_label = tk.Label(             # "done/total done" counter — stored as instance variable so _render_list can update it
            header, text="", bg=BG, fg=SUBTEXT,
            font=("Helvetica", 12),
        )
        self._count_label.pack(side=tk.LEFT, padx=(12, 0), pady=(8, 0))  # 12px left gap; slight top offset to align baseline with title

        # ── entry row ──
        entry_frame = tk.Frame(self.root, bg=BG)  # container for the text entry + Add button so they sit on the same row
        entry_frame.pack(fill=tk.X, padx=24, pady=(18, 0))  # 18px gap below the header

        self._entry_var = tk.StringVar()          # tkinter variable bound to the entry widget; lets us read/clear the text programmatically
        entry = tk.Entry(                         # the single-line text field where users type new tasks
            entry_frame,
            textvariable=self._entry_var,         # two-way binding: changes in the widget update the var and vice versa
            bg=ENTRY_BG, fg=TEXT,                 # dark blue background, light text
            insertbackground=TEXT,                # cursor (caret) colour — must be set explicitly or it may be invisible on dark backgrounds
            relief=tk.FLAT,                       # no 3-D border effect
            font=("Helvetica", 13),
            bd=0,                                 # border width 0 to complement FLAT relief
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, ipadx=12)  # expand=True makes it take all remaining horizontal space
        entry.bind("<Return>", lambda _: self._add_task())  # pressing Enter triggers the same action as clicking Add

        add_btn = tk.Button(                      # the "Add" button to the right of the entry field
            entry_frame, text="  Add  ",
            bg=ACCENT, fg="white", activebackground="#c73652",  # slightly darker red when the button is pressed
            font=("Helvetica", 12, "bold"),
            relief=tk.FLAT, cursor="hand2", bd=0,  # hand cursor signals the button is clickable
            command=self._add_task,               # call _add_task when clicked
        )
        add_btn.pack(side=tk.LEFT, padx=(8, 0), ipady=10, ipadx=4)  # 8px gap between entry and button; vertical padding matches entry height

        # ── separator ──
        tk.Frame(self.root, bg=BORDER, height=1).pack(  # thin 1-pixel horizontal line acting as a visual divider
            fill=tk.X, padx=24, pady=(14, 0)
        )

        # ── scrollable card list ──
        outer = tk.Frame(self.root, bg=BG)        # outer container that holds the canvas + scrollbar side-by-side
        outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=(8, 16))  # expand=True so it grows when the window is resized

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, bd=0)   # canvas is the scroll viewport; highlightthickness=0 removes the focus ring
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)  # vertical scrollbar wired to the canvas
        canvas.configure(yscrollcommand=scrollbar.set)  # keep the scrollbar thumb in sync with canvas scroll position

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)  # scrollbar sits on the right edge, stretches full height
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)  # canvas fills all remaining space to the left of the scrollbar

        self._list_frame = tk.Frame(canvas, bg=BG)  # inner frame placed inside the canvas; all cards are packed into this frame
        self._list_frame_id = canvas.create_window(  # embed the frame as a canvas item so the canvas can scroll it
            (0, 0), window=self._list_frame, anchor="nw"  # position at top-left; anchor="nw" means the frame's top-left corner is at (0,0)
        )

        self._canvas = canvas                     # store canvas reference so scroll helper methods can access it
        self._list_frame.bind("<Configure>", self._on_frame_configure)   # fires whenever the frame's size changes — used to update the scroll region
        canvas.bind("<Configure>", self._on_canvas_configure)            # fires when the canvas is resized — used to keep the frame width in sync
        canvas.bind("<MouseWheel>", self._on_mousewheel)  # Windows/macOS scroll wheel event
        canvas.bind("<Button-4>",   self._on_mousewheel)  # Linux scroll-up button event
        canvas.bind("<Button-5>",   self._on_mousewheel)  # Linux scroll-down button event

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render_list(self):                       # destroys all existing card widgets and redraws them from scratch
        for w in self._list_frame.winfo_children():  # iterate over every widget currently inside the list frame
            w.destroy()                           # remove it — avoids duplicate cards after add/toggle/delete/drag

        for i, item in enumerate(self.todos):     # walk the list with an index so we know each card's position
            self._make_card(i, item)              # build and pack a card widget for this todo item

        total = len(self.todos)                   # total number of tasks in the list
        done  = sum(1 for t in self.todos if t.completed)  # count how many are ticked
        self._count_label.config(text=f"{done}/{total} done")  # update the header counter label

    def _make_card(self, index: int, item: TodoItem):   # builds one card widget for the todo item at the given list index
        is_done = item.completed                  # cache the flag so we don't call item.completed repeatedly
        card_color = DONE_CARD if is_done else CARD_BG   # completed cards use a darker background
        name_color = DONE_TEXT  if is_done else TEXT      # completed task names use a dimmer text colour

        card = tk.Frame(                          # outermost container for the card; everything else is packed inside it
            self._list_frame,
            bg=card_color,
            pady=10, padx=12,                     # internal padding so content doesn't touch the card edges
        )
        card.pack(fill=tk.X, pady=(0, CARD_PAD_Y))  # stretch full width; CARD_PAD_Y pixels of space below each card

        # left accent bar — a narrow vertical stripe of colour on the card's left edge
        accent_bar = tk.Frame(card, bg=DONE_TEXT if is_done else ACCENT, width=3)  # 3px wide; grey when done, red otherwise
        accent_bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))  # fill full card height; 10px gap to the right before the handle

        # drag handle — the braille-dots glyph that signals the card is draggable
        handle = tk.Label(
            card, text="⠿", bg=card_color, fg=SUBTEXT,
            font=("Helvetica", 18), cursor="fleur",  # "fleur" is the four-arrow move cursor, appropriate for drag handles
        )
        handle.pack(side=tk.LEFT, padx=(0, 8))    # 8px gap between handle and checkbox

        # checkbox — lets the user mark the task as complete/incomplete
        check_var = tk.BooleanVar(value=is_done)  # BooleanVar synced to the checkbox visual state; initialised to current completed value
        cb = tk.Checkbutton(
            card,
            variable=check_var,                   # checkbox appearance is driven by this variable
            bg=card_color,                        # match card background so there's no visible checkbox background box
            activebackground=card_color,          # prevent the background changing colour when the checkbox is clicked
            selectcolor=ACCENT2,                  # colour shown inside the checkbox when it is ticked
            fg=ACCENT,                            # colour of the checkmark itself
            activeforeground=ACCENT,              # checkmark colour while the mouse button is held down
            cursor="hand2",                       # pointer cursor to signal it's interactive
            relief=tk.FLAT, bd=0,                 # no border around the checkbox
            command=lambda idx=index: self._toggle(idx),  # idx=index captures the current index in the closure, avoiding the late-binding problem
        )
        cb.pack(side=tk.LEFT)                     # sit the checkbox immediately to the right of the drag handle

        # text block — a sub-frame holding the task name and creation timestamp labels
        text_frame = tk.Frame(card, bg=card_color)  # transparent sub-frame; background matches card so it's invisible
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))  # expand=True lets it take all remaining horizontal space

        name_font = ("Helvetica", 13, "overstrike" if is_done else "normal")  # strikethrough style for completed tasks
        tk.Label(
            text_frame, text=item.name,           # the actual task text
            bg=card_color, fg=name_color,
            font=name_font,
            anchor="w",                           # left-align the text within the label
        ).pack(fill=tk.X)                         # stretch to fill the text_frame width

        tk.Label(
            text_frame,
            text=f"Created: {item.display_created()}",  # human-readable timestamp, e.g. "Created: 22 Mar 2026  14:35"
            bg=card_color, fg=SUBTEXT,
            font=("Helvetica", 9),                # smaller font to de-emphasise the metadata
            anchor="w",
        ).pack(fill=tk.X)

        # delete button — the ✕ on the far right of the card
        del_btn = tk.Button(
            card, text="✕",
            bg=card_color, fg=SUBTEXT,            # unobtrusive grey until hovered
            activebackground=card_color, activeforeground=ACCENT,  # turns red on hover/press
            font=("Helvetica", 12), relief=tk.FLAT, bd=0,
            cursor="hand2",
            command=lambda idx=index: self._delete(idx),  # capture index in closure to avoid late-binding bug
        )
        del_btn.pack(side=tk.RIGHT, padx=(0, 4))  # anchored to the right edge; 4px right margin

        # drag bindings — applied to handle, card body, and text_frame so the whole card is draggable
        for widget in (handle, card, text_frame):
            widget.bind("<ButtonPress-1>",   lambda e, idx=index: self._drag_start(e, idx))  # mouse button down starts the drag
            widget.bind("<B1-Motion>",        self._drag_motion)   # mouse moved while button held — update ghost & drop indicator
            widget.bind("<ButtonRelease-1>",  self._drag_end)      # mouse button released — commit or cancel the reorder

        # hover highlight — subtle background change when the mouse enters/leaves the card
        for widget in (card, text_frame):         # handle excluded because it already has a custom cursor; mixing hover on it causes flicker
            widget.bind("<Enter>", lambda e, c=card, cc=card_color: c.config(bg=CARD_HOVER if cc == CARD_BG else cc))  # only highlight non-completed cards
            widget.bind("<Leave>", lambda e, c=card, cc=card_color: c.config(bg=cc))  # restore original background on mouse leave

    # ── drag & drop ───────────────────────────────────────────────────────────

    def _drag_start(self, event: tk.Event, index: int):   # called when the user presses the mouse button on a card
        self._drag_source = index                 # record which card is being dragged by its list index

        # ghost window — a borderless semi-transparent window that shows the task name and follows the cursor
        item = self.todos[index]                  # look up the todo item being dragged
        ghost = tk.Toplevel(self.root)            # Toplevel creates a separate window; it will float above everything
        ghost.overrideredirect(True)              # remove the OS title bar and borders so it looks like a floating chip
        ghost.attributes("-alpha", 0.75)          # 75% opacity so the user can still see what's underneath
        ghost.configure(bg=CARD_HOVER)
        tk.Label(
            ghost, text=f"  ⠿  {item.name[:40]}",  # show the drag handle glyph + up to 40 chars of the task name
            bg=CARD_HOVER, fg=TEXT,
            font=("Helvetica", 12), padx=10, pady=8,
        ).pack()
        ghost.geometry(f"+{event.x_root + 12}+{event.y_root + 6}")  # position the ghost slightly offset from cursor so it doesn't block the drop target
        self._drag_ghost = ghost                  # store reference so _drag_motion can move it and _drag_end can destroy it

    def _drag_motion(self, event: tk.Event):      # called repeatedly while the mouse moves with the button held down
        if self._drag_ghost:                      # safety check — ghost should always exist during a drag but guard anyway
            self._drag_ghost.geometry(f"+{event.x_root + 12}+{event.y_root + 6}")  # move ghost to follow cursor

        # calculate which position in the list the cursor is currently over
        try:
            rel_y = (
                event.y_root                      # absolute Y position of the cursor on screen
                - self._list_frame.winfo_rooty()  # subtract the list frame's screen Y origin to get a frame-relative position
                + self._canvas.canvasy(0)         # add the canvas scroll offset so dragging works correctly when scrolled down
            )
            n = len(self.todos)                   # total number of items — drop index can be 0 (top) to n (bottom)
            drop = min(max(int(rel_y // (CARD_HEIGHT + CARD_PAD_Y)), 0), n)  # clamp to valid range; floor-divide by card slot height
        except Exception:
            return                                # if geometry info isn't available yet (e.g. during rapid motion), skip this frame

        if drop != self._drop_index:              # only re-render if the target slot has actually changed — avoids unnecessary redraws
            self._drop_index = drop               # update the tracked drop position
            self._render_list_with_drop_hint(drop)  # redraw the list with the red indicator line at the new position

    def _drag_end(self, event: tk.Event):         # called when the user releases the mouse button
        if self._drag_ghost:
            self._drag_ghost.destroy()            # remove the floating ghost window
            self._drag_ghost = None               # clear the reference to free memory

        src = self._drag_source                   # the original index of the card that was dragged
        dst = self._drop_index                    # the index where it should be inserted

        if src is not None and dst is not None and dst != src and dst != src + 1:
            # dst != src means it actually moved; dst != src+1 means it didn't just drop back into its own gap
            item = self.todos.pop(src)            # remove the item from its original position
            if dst > src:
                dst -= 1                          # after popping, every index above src shifts down by 1, so adjust the target
            self.todos.insert(dst, item)          # insert the item at the new position
            save_todos(self.todos)                # persist the new order to JSON immediately

        self._drag_source = None                  # reset drag state so the next drag starts clean
        self._drop_index  = None
        self._render_list()                       # full re-render (without drop hint) to reflect the final order

    def _render_list_with_drop_hint(self, drop_index: int):  # like _render_list but inserts a red line at the potential drop position
        for w in self._list_frame.winfo_children():
            w.destroy()                           # clear existing widgets before rebuilding

        for i, item in enumerate(self.todos):
            if i == drop_index:                   # insert the drop indicator BEFORE the card at this index
                tk.Frame(
                    self._list_frame, bg=DRAG_LINE, height=3  # 3px tall red bar
                ).pack(fill=tk.X, pady=(0, 2))    # small bottom padding so it doesn't merge visually with the card below
            self._make_card(i, item)              # render the card at its current (pre-drop) position

        if drop_index == len(self.todos):         # if the cursor is past the last card, draw the indicator at the very bottom
            tk.Frame(
                self._list_frame, bg=DRAG_LINE, height=3
            ).pack(fill=tk.X, pady=(2, 0))

    # ── actions ───────────────────────────────────────────────────────────────

    def _add_task(self):                          # reads the entry field and appends a new TodoItem to the list
        name = self._entry_var.get().strip()      # get the entry text and strip leading/trailing whitespace
        if not name:
            return                                # do nothing if the field is blank or only whitespace
        new_item = TodoItem(name=name, position=len(self.todos))  # position=len(...) places it at the end; created_at is auto-set
        self.todos.append(new_item)               # add to the in-memory list
        save_todos(self.todos)                    # persist to JSON immediately so no data is lost if the app crashes
        self._entry_var.set("")                   # clear the entry field ready for the next task
        self._render_list()                       # redraw the list so the new card appears

    def _toggle(self, index: int):                # flips the completed state of the task at the given index
        self.todos[index].completed = not self.todos[index].completed  # invert the boolean
        save_todos(self.todos)                    # persist the change
        self._render_list()                       # redraw so the card style (strikethrough, dim colours) updates immediately

    def _delete(self, index: int):                # removes the task at the given index from the list
        self.todos.pop(index)                     # pop() removes and discards the item in one step
        save_todos(self.todos)                    # persist — positions will be re-assigned inside save_todos
        self._render_list()                       # redraw without the deleted card

    # ── scroll helpers ────────────────────────────────────────────────────────

    def _on_frame_configure(self, _event):        # called whenever the list frame's size changes (e.g. cards added/removed)
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))  # update the canvas scroll region to match the new frame size

    def _on_canvas_configure(self, event):        # called whenever the canvas itself is resized (e.g. window resize)
        self._canvas.itemconfig(self._list_frame_id, width=event.width)  # force the embedded list frame to match the canvas width

    def _on_mousewheel(self, event):              # handles scroll-wheel events on all platforms
        if event.num == 4:                        # Linux scroll-up: Button-4 event
            self._canvas.yview_scroll(-1, "units")   # scroll the canvas up by one unit
        elif event.num == 5:                      # Linux scroll-down: Button-5 event
            self._canvas.yview_scroll(1, "units")    # scroll the canvas down by one unit
        else:                                     # Windows/macOS: delta is a multiple of 120 (positive = up, negative = down)
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")  # divide by 120 to get +/-1; negate because tkinter scroll direction is inverted

    # ── close ─────────────────────────────────────────────────────────────────

    def _on_close(self):                          # called when the user clicks the window's X button
        save_todos(self.todos)                    # final save in case any unsaved state exists (belt-and-suspenders — saves already happen on every action)
        self.root.destroy()                       # close the window and end the tkinter event loop


# ── entry point ───────────────────────────────────────────────────────────────

def main():                                       # top-level function that bootstraps the application
    root = tk.Tk()                                # create the root Tk window; there must be exactly one Tk() per application
    TodoApp(root)                                 # instantiate the app, passing in the root window; the constructor builds all UI
    root.mainloop()                               # hand control to tkinter's event loop; this blocks until the window is closed


if __name__ == "__main__":                        # only run main() when this file is executed directly, not when it's imported as a module
    main()