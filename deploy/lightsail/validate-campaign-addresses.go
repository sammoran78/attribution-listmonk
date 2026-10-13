// Parse the saved envelope addresses without connecting to SMTP or sending mail.
package main

import (
	"encoding/json"
	"fmt"
	"net/mail"
	"os"
)

func main() {
	var input struct {
		Before string `json:"before"`
		After string `json:"after"`
		Recipients []struct {
			ID int `json:"id"`
			Email string `json:"email"`
		} `json:"recipients"`
	}
	if err := json.NewDecoder(os.Stdin).Decode(&input); err != nil { panic(err) }
	_, oldErr := mail.ParseAddressList(input.Before)
	if oldErr == nil { panic("Original sender unexpectedly parses") }
	if _, err := mail.ParseAddressList(input.After); err != nil { panic(err) }
	if _, err := mail.ParseAddress(input.After); err != nil { panic(err) }
	invalid := []int{}
	for _, recipient := range input.Recipients {
		if _, err := mail.ParseAddress(recipient.Email); err != nil {
			invalid = append(invalid, recipient.ID)
		}
	}
	if len(invalid) > 0 { panic(fmt.Sprintf("Invalid subscriber address IDs: %v", invalid)) }
	json.NewEncoder(os.Stdout).Encode(map[string]any{
		"original_sender_error": oldErr.Error(), "corrected_sender": input.After,
		"recipients_checked": len(input.Recipients), "invalid_recipient_ids": invalid,
		"smtp_connections": 0, "emails_sent": 0,
	})
}
