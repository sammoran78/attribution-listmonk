package models

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestSubscriberPhone(t *testing.T) {
	for _, phone := range []string{"", "   ", "+61 412 345 678", "0412 345 678", "+1 (212) 555-0100 ext. 23"} {
		t.Run(phone, func(t *testing.T) {
			sub := Subscriber{Attribs: JSON{"city": "Sydney"}}
			if err := sub.SetPhone(" " + phone + " "); err != nil {
				t.Fatal(err)
			}
			// Round-trip through the stored JSON representation.
			value, err := sub.Attribs.Value()
			if err != nil {
				t.Fatal(err)
			}
			saved := Subscriber{Attribs: JSON{}}
			if err := saved.Attribs.Scan(value); err != nil {
				t.Fatal(err)
			}
			if saved.Phone() != strings.TrimSpace(phone) || saved.Attribs["city"] != "Sydney" {
				t.Fatalf("unexpected stored attributes: %#v", saved.Attribs)
			}
			if err := saved.SetPhone(""); err != nil {
				t.Fatal(err)
			}
			if _, ok := saved.Attribs["phone"]; ok || saved.Attribs["city"] != "Sydney" {
				t.Fatalf("clearing phone changed other attributes: %#v", saved.Attribs)
			}
		})
	}
}

func TestSubscriberPhoneOptionalAndLength(t *testing.T) {
	var sub Subscriber
	if sub.Phone() != "" {
		t.Fatal("missing phone should be empty")
	}
	if err := sub.SetPhone(""); err != nil || sub.Attribs != nil {
		t.Fatal("empty phone should not require attributes")
	}
	if err := sub.SetPhone(strings.Repeat("1", 64)); err != nil {
		t.Fatal(err)
	}
	if err := sub.SetPhone(strings.Repeat("1", 65)); err == nil || len(sub.Phone()) != 64 {
		t.Fatal("oversize phone should fail without changing saved phone")
	}
	encoded, err := json.Marshal(sub)
	if err != nil || !strings.Contains(string(encoded), `"phone":"`+sub.Phone()+`"`) {
		t.Fatalf("phone missing from API/export JSON: %s (%v)", encoded, err)
	}
}
