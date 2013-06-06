import sublime
import sublime_plugin
import repl


class WorksheetCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.settings = sublime.load_settings("worksheet.sublime-settings")
        self.timeout = self.settings.get('worksheet_timeout')
        try:
            language = self.get_language()
            self.repl = self.get_repl(language)
            self.remove_previous_results()
            self.process_line(0)
        except repl.ReplStartError, e:
            msg = "Could not start REPL for " + language + ".\n"
            msg += "Tried: " + e.message
            sublime.error_message(msg)

    def get_repl(self, language):
        repl_settings = self.settings.get("worksheet_languages").get(language)
        if repl_settings is not None:
            repl_settings["timeout"] = self.settings.get("worksheet_timeout")
            return repl.Repl(repl_settings.pop("cmd"), **repl_settings)
        sublime.error_message("No worksheet REPL found for " + language)

    def close_repl(self):
        self.repl.close()

    def get_language(self):
        return self.view.settings().get("syntax").split('/')[-1].split('.')[0]

    def remove_previous_results(self):
        edit = self.view.begin_edit("remove_previous_results")
        for region in reversed(self.view.find_all("^" + self.repl.prefix)):
            self.view.erase(edit, self.view.full_line(region))
        self.view.end_edit(edit)

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
        if not (is_last_line or result.is_eof or result.is_timeout):
            self.process_line(next_start)
        else:
            self.set_status('')
            self.close_repl()

    def insert(self, text, start):
        edit = self.view.begin_edit("process_line")
        self.view.insert(edit, start, str(text))
        self.view.end_edit(edit)

    def set_status(self, msg, key="worksheet"):
        self.view.set_status(key, msg % {"language": self.get_language()})
