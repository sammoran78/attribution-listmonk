package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"

	"github.com/knadh/listmonk/models"
	"github.com/labstack/echo/v4"
)

type signupCoreStub struct {
	list     models.List
	existing *models.Subscriber
	saved    models.Subscriber
	ids      []int
	updated  bool
}

func (s *signupCoreStub) GetList(_ int, uuid string) (models.List, error) {
	if uuid != negroMatapacosListUUID {
		panic("wrong list")
	}
	return s.list, nil
}
func (s *signupCoreStub) GetSubscriber(_ int, _ string, _ string) (models.Subscriber, error) {
	return *s.existing, nil
}
func (s *signupCoreStub) InsertSubscriber(sub models.Subscriber, ids []int, uuids []string, confirm, assert bool) (models.Subscriber, bool, error) {
	if confirm || !assert || len(uuids) > 0 {
		panic("unsafe insert")
	}
	if s.existing != nil {
		return models.Subscriber{}, false, echo.NewHTTPError(http.StatusConflict)
	}
	s.saved = sub
	s.ids = ids
	return sub, s.list.Optin == models.ListOptinDouble, nil
}
func (s *signupCoreStub) UpdateSubscriberWithLists(_ int, sub models.Subscriber, ids []int, uuids []string, confirm, deleteLists, assert bool, permitted []int, resubscribe bool) (models.Subscriber, bool, error) {
	if confirm || deleteLists || !assert || len(uuids) > 0 || !resubscribe {
		panic("unsafe update")
	}
	s.saved = sub
	s.ids = ids
	s.updated = true
	return sub, s.list.Optin == models.ListOptinDouble, nil
}
func TestNegroMatapacosValidation(t *testing.T) {
	valid := `{"email":"person@example.invalid","preferred_languages":["Spanish"],"consent":true}`
	for _, body := range []string{valid, strings.ReplaceAll(valid, "Spanish", "English")} {
		if _, err := decodeNegroMatapacosSignup(strings.NewReader(body)); err != nil {
			t.Fatal(err)
		}
	}
	for _, body := range []string{`null`, `{}`, valid + ` {}`, strings.ReplaceAll(valid, "true", "false"), strings.ReplaceAll(valid, "Spanish", "French"), strings.ReplaceAll(valid, `["Spanish"]`, `["English","Spanish"]`), strings.ReplaceAll(valid, `["Spanish"]`, `[]`), strings.ReplaceAll(valid, `"consent":true`, `"consent":true,"attribs":{"admin":true}`), strings.ReplaceAll(valid, `"consent":true`, `"consent":true,"list_uuids":["other"]`)} {
		if _, err := decodeNegroMatapacosSignup(strings.NewReader(body)); err == nil {
			t.Errorf("accepted invalid body: %s", body)
		}
	}
}
func TestNegroMatapacosSubscriberSave(t *testing.T) {
	for _, language := range []string{"English", "Spanish"} {
		for _, existing := range []bool{false, true} {
			core := &signupCoreStub{list: models.List{Base: models.Base{ID: 7}, Type: models.ListTypePublic, Status: models.ListStatusActive, Optin: models.ListOptinSingle}}
			if existing {
				core.existing = &models.Subscriber{Base: models.Base{ID: 99}, Name: "Existing name", Email: "person@example.invalid", Status: models.SubscriberStatusEnabled, Attribs: models.JSON{"keep": "unchanged"}}
			}
			hasOptin, err := saveNegroMatapacosSignup(core, negroMatapacosSignup{Email: "person@example.invalid", Name: "New name", PreferredLanguages: []string{language}, Consent: true})
			if err != nil || hasOptin {
				t.Fatalf("save: %v %v", hasOptin, err)
			}
			if !reflect.DeepEqual(core.ids, []int{7}) || !reflect.DeepEqual(core.saved.Attribs["preferred_languages"], []string{language}) {
				t.Fatalf("wrong save: %+v", core)
			}
			if existing && (core.saved.Name != "Existing name" || core.saved.Attribs["keep"] != "unchanged") {
				t.Fatal("existing subscriber data overwritten")
			}
			data, _ := json.Marshal(core.saved.Attribs)
			if !strings.Contains(string(data), `"preferred_languages":["`+language+`"]`) {
				t.Fatal(string(data))
			}
		}
	}
}
func TestNegroMatapacosSuppressionAndListAvailability(t *testing.T) {
	for _, status := range []string{models.SubscriberStatusBlockListed, models.SubscriberStatusDisabled} {
		core := &signupCoreStub{list: models.List{Type: models.ListTypePublic, Status: models.ListStatusActive}, existing: &models.Subscriber{Status: status}}
		if _, err := saveNegroMatapacosSignup(core, negroMatapacosSignup{}); err != nil || core.updated {
			t.Fatal("suppressed subscriber changed", err)
		}
	}
	for _, list := range []models.List{{}, {Type: models.ListTypePrivate, Status: models.ListStatusActive}, {Type: models.ListTypePublic, Status: models.ListStatusArchived}} {
		if _, err := saveNegroMatapacosSignup(&signupCoreStub{list: list}, negroMatapacosSignup{}); err == nil {
			t.Fatal("unavailable list accepted")
		}
	}
}
func TestNegroMatapacosCORSAndLimits(t *testing.T) {
	e := echo.New()
	calls := 0
	registerNegroMatapacosSignup(e, func(c echo.Context) error { calls++; return c.JSON(200, map[string]bool{"data": true}) })
	request := func(method, origin, body, forwarded string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(method, negroMatapacosSignupPath, strings.NewReader(body))
		req.Header.Set("Origin", origin)
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Forwarded-For", forwarded)
		rec := httptest.NewRecorder()
		e.ServeHTTP(rec, req)
		return rec
	}
	origin := "https://negromatapacos.cl"
	if r := request("OPTIONS", origin, "", ""); r.Code != 204 || r.Header().Get("Access-Control-Allow-Origin") != origin {
		t.Fatal("preflight", r.Code, r.Header())
	}
	for _, origin := range []string{"https://evil.example", "", "https://negromatapacos.cl.evil.example"} {
		if r := request("POST", origin, "{}", ""); r.Code != 403 {
			t.Fatal("origin accepted", r.Code)
		}
	}
	if calls != 0 {
		t.Fatal("forbidden request reached handler")
	}
	if r := request("POST", origin, strings.Repeat("x", 5000), ""); r.Code != 413 {
		t.Fatal("oversized request", r.Code)
	}
	for i := 0; i < 5; i++ {
		if r := request("POST", origin, "{}", "spoofed, 192.0.2.1"); r.Code != 200 {
			t.Fatal("valid request", r.Code)
		}
	}
	if r := request("POST", origin, "{}", "different-spoof, 192.0.2.1"); r.Code != 429 {
		t.Fatal("rate limit bypass", r.Code)
	}
}
