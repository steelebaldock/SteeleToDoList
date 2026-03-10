import tkinter as tk
from tkinter import ttk
import pickle
import os

class TodoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Steele's Todo List")
        self.root.geometry("800x600")
        self.root.configure(bg='#f0f0f0')

        # File path for the pickle file
        self.save_file = "todo_list.pkl"

        # Load existing todos or start with empty list
        self.todos = self.load_todos()

        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        # Save on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_todos(self):
        """Load todos from pickle file, return empty list if file doesn't exist."""
        if os.path.exists(self.save_file):
            with open(self.save_file, "rb") as f:
                return pickle.load(f)
        return []

    def save_todos(self):
        """Save the current todos list to a pickle file."""
        with open(self.save_file, "wb") as f:
            pickle.dump(self.todos, f)

    def add_todo(self, task: str):
        """Add a new task and save."""
        self.todos.append({"task": task, "done": False})
        self.save_todos()

    def remove_todo(self, index: int):
        """Remove a task by index and save."""
        if 0 <= index < len(self.todos):
            self.todos.pop(index)
            self.save_todos()

    def toggle_todo(self, index: int):
        """Mark a task as done/undone and save."""
        if 0 <= index < len(self.todos):
            self.todos[index]["done"] = not self.todos[index]["done"]
            self.save_todos()

    def on_close(self):
        """Save before closing the window."""
        self.save_todos()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = TodoApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()