import sublime
import sublime_plugin
import repl
import os


class WorksheetCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.settings = sublime.load_settings("worksheet.sublime-settings")
        self.timeout = self.settings.get("worksheet_timeout")
        try:
            language = self.get_language()
            repl_def = self.settings.get("worksheet_languages").get(language)
            repl_def["timeout"] = self.settings.get("worksheet_timeout")
            filename = self.view.file_name()
            if filename is not None:
                repl_def["cwd"] = os.dirname(filename)
            self.repl = repl.get_repl(language, repl_def)
        except repl.ReplStartError, e:
            return sublime.error_message(e.msg)
        self.remove_previous_results()
        self.ensure_trailing_newline(edit)
        self.process_line(0)

    def get_language(self):
        return self.view.settings().get("syntax").split('/')[-1].split('.')[0]

    def remove_previous_results(self):
        edit = self.view.begin_edit("remove_previous_results")
        for region in reversed(self.view.find_all("^" + self.repl.prefix)):
            self.view.erase(edit, self.view.full_line(region))
        self.view.end_edit(edit)

    def ensure_trailing_newline(self, edit):
        eof = self.view.size()
        nl = u'\n'
        if self.view.substr(eof - 1) is not nl:
            self.view.insert(edit, eof, nl)

    def process_line(self, start):
        line = self.view.full_line(start)
        line_text = self.view.substr(line)
        self.set_status("Sending 1 line to %(language)s REPL.")
        is_last_line = "\n" not in line_text
        self.queue_thread(
            repl.ReplThread(self.repl, line_text, is_last_line),
            line.end(),
            is_last_line
        ).start()

    def queue_thread(self, thread, start, is_last_line):
        sublime.set_timeout(
            lambda: self.handle_thread(thread, start, is_last_line),
            100
        )
        return thread

    def handle_thread(self, thread, next_start, is_last_line):
        if thread.is_alive():
            self.handle_running_thread(thread, next_start, is_last_line)
        else:
            self.handle_finished_thread(thread, next_start, is_last_line)

    def handle_running_thread(self, thread, next_start, is_last_line):
        self.set_status("Waiting for %(language)s REPL.")
        self.queue_thread(thread, next_start, is_last_line)

    def handle_finished_thread(self, thread, next_start, is_last_line):
        result = thread.result
        self.insert(result, next_start)
        next_start += len(str(result))
        if not (is_last_line or result.terminates):
            self.process_line(next_start)
        else:
            self.set_status('')
            try:
                self.repl.close()
            except repl.ReplCloseError, e:
                sublime.error_message(
                    "Could not close the REPL:\n" + e.message)

    def insert(self, text, start):
        edit = self.view.begin_edit("process_line")
        self.view.insert(edit, start, str(text))
        self.view.end_edit(edit)

    def set_status(self, msg, key="worksheet"):
        self.view.set_status(key, msg % {"language": self.get_language()})
