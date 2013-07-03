import sublime
import sublime_plugin
import repl
import os

# Make sure /usr/local/bin is on the path
exec_path = os.getenv('PATH', '')
if not "/usr/local/bin" in exec_path:
    os.environ["PATH"] = exec_path + os.pathsep + "/usr/local/bin"


class WorksheetCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.load_settings()
        try:
            language = self.get_language()
            default_def = self.settings.get("worksheet_defaults")
            repl_defs = self.settings.get("worksheet_languages")
            repl_def = dict(
                default_def.items() + repl_defs.get(language, {}).items())
            filename = self.view.file_name()
            if filename is not None:
                repl_def["cwd"] = os.path.dirname(filename)
            self.repl = repl.get_repl(language, repl_def)
        except repl.ReplStartError, e:
            return sublime.error_message(e.message)
        self.remove_previous_results()

    def load_settings(self):
        self.settings = sublime.load_settings("worksheet.sublime-settings")
        self.timeout = self.settings.get("worksheet_timeout")

    def get_language(self):
        return self.view.settings().get("syntax").split('/')[-1].split('.')[0]

    def remove_previous_results(self):
        edit = self.view.begin_edit("remove_previous_results")
        for region in reversed(self.view.find_all("^" + self.repl.prefix)):
            self.view.erase(edit, self.view.full_line(region))
        self.view.end_edit(edit)

    def ensure_trailing_newline(self, edit):
        eof = self.view.size()
        if len(self.view.substr(self.view.line(eof)).strip()) is not 0:
            self.view.insert(edit, eof, "\n")

    def process_line(self, start):
        line = self.view.full_line(start)
        line_text = self.view.substr(line)
        if "\n" in line_text:
            self.view.add_regions("worksheet", list([line]), "string")
            self.set_status("Sending 1 line to %(language)s REPL.")
            self.queue_thread(
                repl.ReplThread(self.repl, line_text),
                line.end(),
            ).start()
        else:
            self.cleanup()

    def queue_thread(self, thread, start):
        sublime.set_timeout(
            lambda: self.handle_thread(thread, start),
            100
        )
        return thread

    def handle_thread(self, thread, next_start):
        if thread.is_alive():
            self.handle_running_thread(thread, next_start)
        else:
            self.handle_finished_thread(thread, next_start)

    def handle_running_thread(self, thread, next_start):
        self.set_status("Waiting for %(language)s REPL.")
        self.queue_thread(thread, next_start)

    def handle_finished_thread(self, thread, next_start):
        self.view.add_regions("worksheet", list(), "string")
        result = thread.result
        self.insert(result, next_start)
        next_start += len(str(result))
        if not result.terminates:
            self.process_line(next_start)
        else:
            self.cleanup()

    def insert(self, text, start):
        edit = self.view.begin_edit("process_line")
        self.view.insert(edit, start, str(text))
        self.view.end_edit(edit)

    def set_status(self, msg, key="worksheet"):
        self.view.set_status(key, msg % {"language": self.get_language()})

    def cleanup(self):
        self.set_status('')
        try:
            self.repl.close()
        except repl.ReplCloseError, e:
            sublime.error_message(
                "Could not close the REPL:\n" + e.message)


class WorksheetEvalCommand(WorksheetCommand):
    def run(self, edit):
        WorksheetCommand.run(self, edit)
        self.ensure_trailing_newline(edit)
        self.process_line(0)


class WorksheetClearCommand(WorksheetCommand):
    def run(self, edit):
        WorksheetCommand.run(self, edit)
