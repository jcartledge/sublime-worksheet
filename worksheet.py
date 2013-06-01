import sublime
import sublime_plugin
import threading
import repl


class WorksheetCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.repl = self.get_repl()
        if self.repl is not None:
            self.remove_previous_results()
            self.repl.correspond('')
            self.process_line(0)

    def get_repl(self):
        settings = sublime.load_settings("worksheet.sublime-settings")
        languages = settings.get('worksheet_languages')
        view_settings = self.view.settings()
        language = view_settings.get('syntax').split('/')[-1].split('.')[0]
        if language in languages:
            repl_settings = languages.get(language)
            args = repl_settings.get('args')
            del repl_settings['args']
            return repl.Repl(args, **repl_settings)
        else:
            sublime.error_message('No worksheet REPL found for ' + language)

    def remove_previous_results(self):
        view = self.view
        edit = view.begin_edit('remove_previous_results')
        for region in reversed(view.find_all("^" + self.repl.prefix)):
            view.erase(edit, view.full_line(region))
        self.view.end_edit(edit)

    def process_line(self, start):
        view = self.view
        line = view.full_line(start)
        next_start = line.end()
        line_text = view.substr(line)
        is_last_line = "\n" not in line_text
        if is_last_line:
            next_start += 1
            line_text += "\n"
        thread = ReplThread(self.repl, line_text)
        self.queue_thread(thread, next_start, is_last_line)
        thread.start()

    def queue_thread(self, thread, start, is_last_line):
        sublime.set_timeout(
            lambda: self.handle_result(thread, start, is_last_line),
            100
        )

    def handle_result(self, thread, next_start, is_last_line):
        if thread.is_alive():
            self.queue_thread(thread, next_start, is_last_line)
        else:
            edit = self.view.begin_edit('process_line')
            self.view.insert(edit, next_start, thread.result)
            self.view.end_edit(edit)
            next_start += len(thread.result)
            if not is_last_line:
                self.process_line(next_start)


class ReplThread(threading.Thread):
    def __init__(self, repl, str):
        self.repl = repl
        self.str = str
        self.result = None
        threading.Thread.__init__(self)

    def run(self):
        if not self.is_processable():
            self.result = ''
        else:
            result = self.repl.correspond(self.str)
            self.result = '\n'.join([
                self.repl.prefix + line for line in result.split("\n")[:-1]
            ]) + '\n'
            if len(self.result.strip()) is 0:
                self.result = ''

    def is_processable(self):
        return len(self.str.strip()) > 0

