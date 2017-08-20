used_receipts: public(bool[num])

def add_used_receipt(receipt_id: num):
    self.used_receipts[receipt_id] = True
