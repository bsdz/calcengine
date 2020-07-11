        if True:
            et = [k for k, v in QEvent.__dict__.items() if v == event.type()][0]
            if et not in ["HoverEnter", "HoverMove", "HoverLeave", "CursorChange"] :
                sts = [k for k, v in self.__dict__.items() if v == self.state()]
                st = sts[0] if sts else str(self.state())
                ek = [k for k, v in Qt.__dict__.items() if v == event.key()][0] if hasattr(event, "key") else ""
                print(f"{et} / {st} / {ek}"