package main

import (
	"bytes"
	"html"
	"html/template"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"regexp"
	"strings"
	"testing"

	"github.com/knadh/listmonk/internal/i18n"
	"github.com/knadh/listmonk/internal/subimporter"
	"github.com/knadh/listmonk/models"
	"github.com/labstack/echo/v4"
)

func phoneTestLanguage(t *testing.T) *i18n.I18n {
	t.Helper()
	b, err := os.ReadFile("../i18n/en.json")
	if err != nil {
		t.Fatal(err)
	}
	l, err := i18n.New(b)
	if err != nil {
		t.Fatal(err)
	}
	return l
}

func TestPublicSignupRejectsOversizePhone(t *testing.T) {
	l := phoneTestLanguage(t)
	a := &App{i18n: l, importer: subimporter.New(subimporter.Options{}, nil, l)}
	for _, contentType := range []string{echo.MIMEApplicationJSON, echo.MIMEApplicationForm} {
		t.Run(contentType, func(t *testing.T) {
			phone := strings.Repeat("1", 65)
			body := `{"email":"phone@example.com","phone":"` + phone + `","list_uuids":["test"]}`
			if contentType == echo.MIMEApplicationForm {
				body = url.Values{"email": {"phone@example.com"}, "phone": {phone}, "l": {"test"}}.Encode()
			}
			req := httptest.NewRequest(http.MethodPost, "/subscription/form", strings.NewReader(body))
			req.Header.Set(echo.HeaderContentType, contentType)
			ctx := echo.New().NewContext(req, httptest.NewRecorder())
			_, err := a.processSubForm(ctx)
			httpErr, ok := err.(*echo.HTTPError)
			if !ok || httpErr.Code != http.StatusBadRequest || httpErr.Message != l.T("subscribers.invalidPhone") {
				t.Fatalf("expected phone validation before database access, got %v", err)
			}
		})
	}
}

func TestSubscriberPreferencesRenderPhone(t *testing.T) {
	l := phoneTestLanguage(t)
	tpl := template.New("phone-test").Funcs(template.FuncMap{"L": func() *i18n.I18n { return l }})
	tpl, err := tpl.Parse(`{{define "header"}}{{end}}{{define "footer"}}{{end}}`)
	if err != nil {
		t.Fatal(err)
	}
	tpl, err = tpl.ParseFiles("../static/public/templates/subscription.html")
	if err != nil {
		t.Fatal(err)
	}
	for _, phone := range []string{"", "+61 0412 345 678", `" autofocus onfocus="alert(1)`} {
		sub := models.Subscriber{Attribs: models.JSON{"phone": phone}}
		var out bytes.Buffer
		if err := tpl.ExecuteTemplate(&out, "subscription", tplData{Data: unsubTpl{Subscriber: sub, ShowManage: true}}); err != nil {
			t.Fatal(err)
		}
		match := regexp.MustCompile(`name="phone" value="([^"]*)"`).FindStringSubmatch(out.String())
		if len(match) != 2 || html.UnescapeString(match[1]) != phone {
			t.Fatalf("phone missing or unescaped in rendered preferences: %s", out.String())
		}
	}
}
